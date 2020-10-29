"""
Copied from pytest
"""

from _pytest.assertion import truncate
from _pytest.assertion import util


def activate_assert_rewrite(item):
    def callbinrepr(op, left, right):
        hook_result = item.ihook.pytest_assertrepr_compare(
            config=item.config, op=op, left=left, right=right
        )
        for new_expl in hook_result:
            if new_expl:
                new_expl = truncate.truncate_if_required(new_expl, item)
                new_expl = [line.replace("\n", "\\n") for line in new_expl]
                res = "\n~".join(new_expl)
                if item.config.getvalue("assertmode") == "rewrite":
                    res = res.replace("%", "%%")
                return res
        return None

    util._reprcompare = callbinrepr
