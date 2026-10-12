import uuid
import pytest
from fastapi import HTTPException
from backend import main


def test_ownership_is_checked_with_both_identifiers(monkeypatch):
    sid,uid=uuid.uuid4(),uuid.uuid4()
    captured=[]
    def query(sql,args):
        captured.append((sql,args))
        return None
    monkeypatch.setattr(main.db,'one',query)
    with pytest.raises(HTTPException) as error:
        main.owned(sid,uid)
    assert error.value.status_code == 404
    assert captured[0][1] == (sid,uid)
    assert 'user_id=%s' in captured[0][0]


def test_foreign_artifact_content_is_not_returned(monkeypatch):
    monkeypatch.setattr(main.db,'one',lambda *args:None)
    with pytest.raises(HTTPException) as error:
        main.artifact(uuid.uuid4(),uuid.uuid4())
    assert error.value.status_code == 404
