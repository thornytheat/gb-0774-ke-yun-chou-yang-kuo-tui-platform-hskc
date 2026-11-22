from app.config import DISCLOSURE, SPEC
from app.modules.ledger.identity import canonical, sha

from .audit import authenticate


def build_publication(manifest, disclosure, excluded_summary):
    """签发页与下载件共用同一版公开包：不含原始答卷，原件仅留内部归档。"""
    return dict(
        manifest=dict(
            id=manifest['id'],
            files=manifest['files'],
            version=manifest['version'],
            disclosure=DISCLOSURE,
            result_sha256=manifest['result_sha256'],
            created=manifest['created'],
        ),
        disclosure=disclosure,
        excluded=excluded_summary,
    )


def sign(payload):
    return dict(**payload, seal=sha(canonical(payload)), verified=True)


def issue(store, manifest, tables, results):
    """内部复核通过后签发公开包；同批重复签发只登记一次，印章保持不变。"""
    authenticate(manifest, tables, results)
    disclosure = results['disclosure']
    excluded_summary = dict(
        intake=len(results['returns']['rejected']),
        alignment=len(results['frame']['invalid']),
        nonresponse=len(results['frame']['nonresponse']),
    )
    package = sign(build_publication(manifest, disclosure, excluded_summary))
    record = store.register_issuance(manifest['id'], package['seal'], DISCLOSURE, SPEC)
    return package, record
