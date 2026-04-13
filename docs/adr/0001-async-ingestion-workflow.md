# ADR 0001: Asynchronous Ingestion Workflow for Milestone 3

- Status: Proposed
- Date: 2026-04-13
- Deciders: Tech lead, backend team
- Context: The system must expose a production-ready ingestion workflow that allows callers to submit a public URL, perform nested scraping and embedding asynchronously, and poll job progress via a status endpoint.

## Decision

The Milestone 3 ingestion workflow will use an asynchronous request-reply pattern with an API submission endpoint that returns `202 Accepted` and a stable `job_id` for caller polling.

The public ingestion contract will be: a caller POSTs a URL to the ingestion API, receives a response containing:
- HTTP `202 Accepted`
- a stable `job_id`
- a `status_url` in the response body
- a `Location` response header pointing to the same status resource
- an optional `Retry-After` response header when supported

A separate caller-facing status endpoint will exist so clients can poll job progress without waiting for long-running work inside the initial request.

Long-running work will not execute in the request-response cycle. The API will accept and validate the submission, persist the job record, enqueue the work item, then return immediately.

A queue-based worker architecture will process ingestion jobs asynchronously. Azure Service Bus Queue is the default queue technology for Milestone 3.

Large page text and chunk text will be stored in Azure Blob Storage. Qdrant will store vector embeddings plus compact metadata and blob references only, not the full extracted page or chunk body.

The architecture will support containerized deployment on Azure App Service custom containers or Azure Kubernetes Service (AKS).

## Caller-facing async contract

### Ingestion submission endpoint

- Method: `POST`
- Path: `/api/v1/ingest` (or equivalent ingestion job creation endpoint)
- Request body:
  - `url`: string containing the public URL to ingest
- Response:
  - `202 Accepted`
  - Headers:
    - `Location`: URL of the job status resource
    - `Retry-After`: optional when the API can recommend a retry interval
  - Body JSON:
    - `job_id`: stable identifier for the ingestion job
    - `status_url`: same resource as the `Location` header
    - `status`: initial job state such as `accepted`

### Job status endpoint

- Method: `GET`
- Path: `/api/v1/jobs/{job_id}` or `/api/v1/ingestion-jobs/{job_id}`
- Response:
  - HTTP `200 OK` when the job exists
  - Body includes current status and any progress metadata
  - Job lifecycle states include: `accepted`, `queued`, `running`, `completed`, `failed`, `partially_completed`

## Workflow

The expected Milestone 3 workflow is:

1. Caller submits URL to ingestion API.
2. API validates request.
3. API creates job record with status `accepted`.
4. API enqueues work item to Azure Service Bus.
5. API returns `202 Accepted` with `job_id`, `status_url`, and `Location` header.
6. Worker receives job and updates status to `queued` / `running`.
7. Worker crawls root page and nested links within configured limits.
8. Worker extracts content and stores full page text in Azure Blob Storage.
9. Worker chunks extracted text with overlap.
10. Worker stores chunk text in Azure Blob Storage.
11. Worker generates embeddings with bounded concurrency and rate control.
12. Worker upserts vectors into Qdrant with compact metadata and blob references.
13. Worker updates final job status to `completed`, `failed`, or `partially_completed`.

## Architecture components

- Ingestion API: public REST endpoint for job submission and status polling.
- Job metadata store: persisted job records with stable `job_id`, status, timestamps, and progress.
- Azure Service Bus Queue: default asynchronous queue for job dispatch.
- Worker pool: consumer processes that dequeue jobs, perform crawling/scraping, chunking, embedding, and upsert to Qdrant.
- Azure Blob Storage: persistent storage for large page text and chunk text.
- Qdrant: vector store holding embeddings plus compact metadata and blob references.

## Data placement

- Azure Blob Storage stores the full extracted page content and chunk text payloads.
- Qdrant stores only embeddings, compact metadata, and references to the blob objects.
- This keeps Qdrant payloads small and avoids storing large unstructured text directly in the vector database.

## Queue technology decision

Azure Service Bus Queue is the default technology for Milestone 3 because:
- it supports reliable asynchronous request-reply workflows,
- it integrates with Azure-hosted worker platforms,
- it aligns with containerized deployment on Azure App Service custom containers and AKS,
- it cleanly decouples API submission from long-running scraping and vectorization processing.

## Deployment requirements

The system must be deployable in containerized form using:
- Azure App Service custom containers
- Azure Kubernetes Service (AKS)

The implementation should avoid Azure-hosting-specific runtime assumptions in the API layer and keep configuration reusable for both container platforms.

## Out of scope for Milestone 3

The following items are explicitly not part of Milestone 3 unless later added in a separate issue:

- semantic search API
- delete or reprocess API
- authentication or authorization
- multi-tenant isolation
- advanced robots.txt policy management
- sitemap ingestion
- website rendering via headless browser unless explicitly required later

## Consequences

- The public API is more predictable and testable because submission and processing are decoupled.
- Callers poll a stable status resource rather than waiting for scraping and embedding to finish.
- Azure Blob Storage avoids bloating Qdrant with large text payloads.
- Azure Service Bus Queue provides a production-grade default queue for Azure-hosted deployments.
- Early architecture decisions are documented before implementation begins.
