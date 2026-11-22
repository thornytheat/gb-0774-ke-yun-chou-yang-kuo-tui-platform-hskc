import pytest

from app.errors import SurveyProblem
from app.modules.ledger.identity import canonical, sha
from app.modules.ledger.service import archive
from app.modules.ledger.storage import Archive
from app.modules.release.audit import authenticate
from app.modules.release.service import build_publication, issue, sign


@pytest.fixture
def archived(tmp_path,tables):
    store=Archive(tmp_path/'seal.db')
    key=archive(store,tables)['id']
    return store, store.read(key)


def test_seal_recompute(archived):
    store,(manifest,tables,results)=archived
    package,record=issue(store,manifest,tables,results)
    actual=package.pop('seal')
    assert package.pop('verified') and actual==sha(canonical(package))
    assert record['id']==manifest['id'] and record['seal']==actual


def test_publication_has_no_originals(archived):
    store,(manifest,tables,results)=archived
    package,_=issue(store,manifest,tables,results)
    assert 'originals' not in package
    assert 'results' not in package
    assert package['manifest']['result_sha256']==manifest['result_sha256']


def test_page_and_download_same_payload(archived):
    store,(manifest,tables,results)=archived
    downloaded,_=issue(store,manifest,tables,results)
    preview=sign(build_publication(
        manifest,results['disclosure'],
        dict(intake=len(results['returns']['rejected']),
             alignment=len(results['frame']['invalid']),
             nonresponse=len(results['frame']['nonresponse']))))
    assert preview == downloaded


def test_bad_original_still_rejected_internally(archived):
    store,(manifest,tables,results)=archived
    tables['returns']+='\n'
    with pytest.raises(SurveyProblem) as error:
        authenticate(manifest,tables,results)
    assert error.value.code=='BAD_SEAL'


def test_bad_results_still_rejected_internally(archived):
    store,(manifest,tables,results)=archived
    results['balance']['estimated']=0
    with pytest.raises(SurveyProblem) as error:
        issue(store,manifest,tables,results)
    assert error.value.status==409


def test_does_not_release_unbalanced(archived):
    store,(manifest,tables,results)=archived
    results['balance']['balanced']=False
    manifest['result_sha256']=sha(canonical(results))
    with pytest.raises(SurveyProblem) as error:
        issue(store,manifest,tables,results)
    assert error.value.code=='UNBALANCED'


def test_evidence_keeps_exclusion_counts(archived):
    store,(manifest,tables,results)=archived
    package,_=issue(store,manifest,tables,results)
    assert package['excluded']=={'intake':6,'alignment':4,'nonresponse':2}


def test_reissue_same_run_does_not_duplicate(archived):
    store,(manifest,tables,results)=archived
    first,record_one=issue(store,manifest,tables,results)
    second,record_two=issue(store,manifest,tables,results)
    assert first['seal']==second['seal']
    assert record_one['seal']==record_two['seal']
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM issuances').fetchone()[0]==1


def test_api_export(client):
    key=client.post('/api/runs',json={'sample':'dirty'}).json['id']
    response=client.get('/api/export/'+key)
    assert response.headers['Content-Disposition'].startswith('attachment;')
    body=response.json
    assert 'originals' not in body and body['verified']
    assert body['disclosure']['city']['unknown']==40
    again=client.get('/api/export/'+key)
    assert again.json['seal']==body['seal'] and again.json['issuance']['seal']==body['seal']
    run_doc=client.get('/api/runs/'+key).json
    assert run_doc['issuance']['seal']==body['seal']
