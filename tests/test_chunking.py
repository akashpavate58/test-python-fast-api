from app.models.ingestion import BlobReference
from app.services.chunking import chunk_page_text


def make_blob_reference(submitted_url: str, page_url: str) -> BlobReference:
    return BlobReference(
        submitted_url=submitted_url,
        page_url=page_url,
        container_name="raw-pages",
        blob_name="job/pages/abcdef.txt",
        uri="https://example.com/blob/job/pages/abcdef.txt",
    )


def test_chunk_page_text_empty_content_returns_no_chunks() -> None:
    chunks = chunk_page_text(
        job_id="job-1",
        submitted_url="https://example.com",
        page_url="https://example.com/page",
        page_blob_reference=make_blob_reference(
            "https://example.com", "https://example.com/page"
        ),
        text="",
        chunk_size_chars=10,
        chunk_overlap_chars=2,
        min_non_whitespace_chars=1,
    )

    assert chunks == []


def test_chunk_page_text_near_empty_content_skips_chunk() -> None:
    chunks = chunk_page_text(
        job_id="job-2",
        submitted_url="https://example.com",
        page_url="https://example.com/page",
        page_blob_reference=make_blob_reference(
            "https://example.com", "https://example.com/page"
        ),
        text="   \n  ",
        chunk_size_chars=10,
        chunk_overlap_chars=2,
        min_non_whitespace_chars=1,
    )

    assert chunks == []


def test_chunk_page_text_respects_chunk_size_and_overlap() -> None:
    text = "abcdefghijklmnopqrstuvwxyz"
    chunks = chunk_page_text(
        job_id="job-3",
        submitted_url="https://example.com",
        page_url="https://example.com/page",
        page_blob_reference=make_blob_reference(
            "https://example.com", "https://example.com/page"
        ),
        text=text,
        chunk_size_chars=10,
        chunk_overlap_chars=4,
        min_non_whitespace_chars=1,
    )

    assert len(chunks) == 4
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2, 3]
    assert [chunk.total_chunks for chunk in chunks] == [4, 4, 4, 4]
    assert [chunk.start_index for chunk in chunks] == [0, 6, 12, 18]
    assert [chunk.end_index for chunk in chunks] == [10, 16, 22, 26]
    assert [chunk.text for chunk in chunks] == [
        "abcdefghij",
        "ghijklmnop",
        "mnopqrstuv",
        "stuvwxyz",
    ]
    assert len({chunk.chunk_id for chunk in chunks}) == 4


def test_chunk_page_text_maintains_stable_chunk_ids_across_runs() -> None:
    page_blob_reference = make_blob_reference(
        "https://example.com", "https://example.com/page"
    )
    first = chunk_page_text(
        job_id="job-4",
        submitted_url="https://example.com",
        page_url="https://example.com/page",
        page_blob_reference=page_blob_reference,
        text="abcdefghij12345",
        chunk_size_chars=10,
        chunk_overlap_chars=3,
        min_non_whitespace_chars=1,
    )
    second = chunk_page_text(
        job_id="job-4",
        submitted_url="https://example.com",
        page_url="https://example.com/page",
        page_blob_reference=page_blob_reference,
        text="abcdefghij12345",
        chunk_size_chars=10,
        chunk_overlap_chars=3,
        min_non_whitespace_chars=1,
    )

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.start_index for chunk in first] == [chunk.start_index for chunk in second]
    assert [chunk.end_index for chunk in first] == [chunk.end_index for chunk in second]


def test_chunk_page_text_handles_last_chunk_boundaries() -> None:
    text = "abcdefghijklm"
    chunks = chunk_page_text(
        job_id="job-5",
        submitted_url="https://example.com",
        page_url="https://example.com/page",
        page_blob_reference=make_blob_reference(
            "https://example.com", "https://example.com/page"
        ),
        text=text,
        chunk_size_chars=10,
        chunk_overlap_chars=3,
        min_non_whitespace_chars=1,
    )

    assert len(chunks) == 2
    assert chunks[0].start_index == 0
    assert chunks[0].end_index == 10
    assert chunks[1].start_index == 7
    assert chunks[1].end_index == 13
    assert chunks[0].text == "abcdefghij"
    assert chunks[1].text == "hijklm"
