# Third-party material

The committed srxy snapshot excerpted in `data/coding_memory.json` is from
https://github.com/illescasDaniel/srxy at `72bab1dbdc649fbd3d5f739ef73e39394e5db595`.
Its MIT copyright/permission notice is preserved in `data/licenses/srxy.LICENSE`.

RAW-RAG and TencentDB Agent Memory are fetched into ignored `vendor/` directories at pinned commits. Their own licenses
and notices remain with those checkouts. Both repositories declare MIT; third-party dependencies retain their own
licenses. This workspace imports RAW-RAG's code rather than copying its retrieval implementation into this package.

The jev-mem package is a required dependency (MIT). The memory-bank design reference is
https://github.com/illescasDaniel/memory-bank; no copy of its skill is installed by this workspace.

Embedding/reranking weights download separately through FastEmbed and retain their respective model licenses.
Provider API terms and metering apply to explicitly selected hosted calls. No credentials are included.

The optional QSIV runtime and weights are fetched separately from https://huggingface.co/djinn-san/QSIV at revision f1ee842daf758c0ab535cf7d281c85439d6e4b25. Its Apache-2.0 LICENSE and NOTICE remain with that checkout; neither runtime code nor weights are bundled here.
