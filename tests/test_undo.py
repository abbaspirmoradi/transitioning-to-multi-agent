"""Chapter 13: rollback compensates in reverse order and reports what it could not reverse."""
from agentmigration.undo import WriteRecord, rollback

deleted = []


def test_rollback_reverse_order_with_honest_report():
    deleted.clear()
    writes = [WriteRecord("post_comment", "delete_comment", {"comment_id": 1}),
              WriteRecord("post_comment", "delete_comment", {"comment_id": 2}),
              WriteRecord("merge_pull_request", "revert_merge", {"sha": "abc"}, window_open=lambda: False),
              WriteRecord("send_email", None, {})]
    rep = rollback(writes, {"delete_comment": lambda comment_id: deleted.append(comment_id), "revert_merge": lambda sha: None})
    assert deleted == [2, 1]
    assert rep.reversed == ["post_comment", "post_comment"]
    assert ("merge_pull_request", "window closed") in rep.not_reversed
    assert ("send_email", "no inverse declared") in rep.not_reversed
    assert "cannot be reversed" in str(rep)
