from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from ouroboros.indexing import (
    GitHubPublicClient,
    IndexPolicy,
    IndexRunner,
    IndexTarget,
    IndexingError,
    JsonlCorpus,
    RepositorySnapshot,
    compact_measurement,
    extract_github_archive,
    load_manifest,
)


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = io.BytesIO(payload)

    def read(self, size: int = -1) -> bytes:
        return self.payload.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _tar(path: Path, entries: list[tuple[str, bytes | None, str]]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, data, kind in entries:
            member = tarfile.TarInfo(name)
            if kind == "file":
                assert data is not None
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            elif kind == "dir":
                member.type = tarfile.DIRTYPE
                archive.addfile(member)
            elif kind == "symlink":
                member.type = tarfile.SYMTYPE
                member.linkname = "../outside"
                archive.addfile(member)
            else:
                raise AssertionError(kind)


def test_inaugural_style_manifest_is_reusable(tmp_path: Path):
    manifest = tmp_path / "targets.json"
    manifest.write_text(
        json.dumps(
            {
                "selection": "ignored descriptive metadata",
                "targets": [
                    {"repo": "owner/one", "sha": "a" * 40, "stars": 99},
                    {"repository": "owner/two", "sha": "b" * 40},
                ],
            }
        ),
        encoding="utf-8",
    )
    assert load_manifest(manifest) == [
        IndexTarget("owner/one", "a" * 40),
        IndexTarget("owner/two", "b" * 40),
    ]


def test_archive_extraction_strips_github_root_and_never_follows_links(tmp_path: Path):
    archive = tmp_path / "repo.tar.gz"
    _tar(
        archive,
        [
            ("owner-repo-sha/", None, "dir"),
            ("owner-repo-sha/src/", None, "dir"),
            ("owner-repo-sha/src/app.py", b"print('safe')\n", "file"),
        ],
    )
    files, size = extract_github_archive(
        archive,
        tmp_path / "checkout",
        max_files=10,
        max_extracted_bytes=1024,
    )
    assert files == 1
    assert size == len(b"print('safe')\n")
    assert (tmp_path / "checkout/src/app.py").read_text() == "print('safe')\n"

    unsafe = tmp_path / "unsafe.tar.gz"
    _tar(unsafe, [("root/link", None, "symlink")])
    with pytest.raises(IndexingError, match="Unsupported archive member"):
        extract_github_archive(
            unsafe,
            tmp_path / "unsafe-checkout",
            max_files=10,
            max_extracted_bytes=1024,
        )


def test_archive_rejects_path_traversal_and_extraction_limits(tmp_path: Path):
    traversal = tmp_path / "traversal.tar.gz"
    _tar(traversal, [("root/../escape.txt", b"x", "file")])
    with pytest.raises(IndexingError) as error:
        extract_github_archive(
            traversal,
            tmp_path / "traversal-checkout",
            max_files=10,
            max_extracted_bytes=1024,
        )
    assert error.value.code == "unsafe-archive"

    large = tmp_path / "large.tar.gz"
    _tar(large, [("root/a.bin", b"12345", "file")])
    with pytest.raises(IndexingError) as error:
        extract_github_archive(
            large,
            tmp_path / "large-checkout",
            max_files=10,
            max_extracted_bytes=4,
        )
    assert error.value.code == "extracted-too-large"


def test_github_resolution_pins_default_branch_to_exact_sha():
    sha = "c" * 40
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        if request.full_url.endswith("/repos/owner/repo"):
            return FakeResponse(
                json.dumps(
                    {
                        "id": 123,
                        "private": False,
                        "default_branch": "main",
                        "size": 42,
                        "html_url": "https://github.com/owner/repo",
                    }
                ).encode()
            )
        if request.full_url.endswith("/commits/main"):
            return FakeResponse(json.dumps({"sha": sha}).encode())
        raise AssertionError(request.full_url)

    snapshot = GitHubPublicClient(opener=opener).resolve(IndexTarget("owner/repo"))
    assert snapshot.repository_id == 123
    assert snapshot.sha == sha
    assert snapshot.archive_url.endswith(f"/tarball/{sha}")
    assert calls[-1].endswith("/commits/main")


def test_corpus_dedup_only_uses_successful_exact_identities(tmp_path: Path):
    corpus = JsonlCorpus(tmp_path / "index.jsonl")
    corpus.append({"status": "failed", "identity": {"key": "failed-key"}})
    corpus.append({"status": "ok", "identity": {"key": "good-key"}})
    assert corpus.successful_identity_keys() == {"good-key"}


class FakeMetric:
    def __init__(self, **values):
        self.values = values

    def to_dict(self):
        return dict(self.values)


class FakeCategory:
    def __init__(self, value: str):
        self.value = value


class FakeRelationship:
    def __init__(self, value: str):
        self.value = value


def _fake_analysis():
    baseline = SimpleNamespace(
        metrics=FakeMetric(
            direct_product_share=0.5,
            product_plus_essential_share=0.6,
            tooling_share=0.4,
            meta_machinery_share=0.01,
            assurance_ratio=0.1,
            audit_ratio=0.02,
            scaffolding_ratio=0.8,
            far_from_value_share=0.03,
            max_audit_depth=2,
            ouroboros_index=8.0,
            category_code_lines={"core-product": 50, "testing": 40},
        ),
        warnings=["bounded warning"],
        directory_profiles=[],
    )
    product = SimpleNamespace(
        category=FakeCategory("core-product"),
        path="app.py",
        qualified_name="run",
    )
    audit = SimpleNamespace(
        category=FakeCategory("audit-provenance"),
        path="audit.py",
        qualified_name="check",
    )
    chain = SimpleNamespace(
        depth=1,
        symbol_ids=["product", "audit"],
        categories=[product.category, audit.category],
        relationships=[FakeRelationship("calls")],
    )
    semantic = SimpleNamespace(
        metrics=FakeMetric(
            symbol_count=2,
            relationship_count=1,
            resolved_relationships=1,
            probable_relationships=0,
            unresolved_relationships=0,
            product_symbols=1,
            machinery_symbols=1,
            audit_symbols=1,
            meta_symbols=0,
            product_reachable_symbols=2,
            far_from_value_symbols=0,
            max_value_distance=1,
            max_recursive_depth=1,
            direct_product_symbol_share=0.5,
            machinery_symbol_share=0.5,
            audit_symbol_share=0.5,
            meta_symbol_share=0.0,
            scaffolding_symbol_ratio=1.0,
            far_from_value_symbol_share=0.0,
            resolution_rate=1.0,
            exact_resolution_rate=1.0,
            semantic_ouroboros_index=2.5,
            chain_expansions=1,
            chain_truncated=False,
        ),
        symbols={"product": product, "audit": audit},
        chains=[chain],
        diagnostics=[],
    )
    return baseline, semantic


def test_runner_skips_before_acquisition_when_exact_identity_already_succeeded():
    snapshot = RepositorySnapshot(
        repository="owner/repo",
        repository_id=123,
        sha="d" * 40,
        default_branch="main",
        size_kib=10,
        archive_url="https://example.invalid/archive",
        html_url="https://github.com/owner/repo",
    )

    class Client:
        def resolve(self, target):
            return snapshot

    class Acquirer:
        def acquire(self, snapshot, destination):
            raise AssertionError("unchanged HEAD must not be acquired")

    runner = IndexRunner(
        client=Client(),
        policy=IndexPolicy(),
        analyzer_version="0.4.0",
        analyzer_source_revision="e" * 40,
        analyze=lambda path: (_ for _ in ()).throw(AssertionError("must not analyze")),
        acquirer=Acquirer(),
    )
    key = snapshot.identity_key("0.4.0", "e" * 40)
    record = runner.run(IndexTarget("owner/repo"), successful_identity_keys={key})
    assert record["status"] == "skipped"
    assert record["reason"]["code"] == "unchanged-head"


def test_compact_measurement_keeps_axes_and_exact_chain_evidence():
    baseline, semantic = _fake_analysis()
    measurement = compact_measurement(baseline, semantic)
    assert measurement["baseline"]["tooling_share"] == 0.4
    assert measurement["semantic"]["semantic_ouroboros_index"] == 2.5
    assert measurement["category_symbol_counts"] == {
        "audit-provenance": 1,
        "core-product": 1,
    }
    assert measurement["representative_deepest_chains"][0]["canonical_resolution"] == "exact"
