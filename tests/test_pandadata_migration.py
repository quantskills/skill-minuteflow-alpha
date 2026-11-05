import ast
import datetime
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def functions(relative, names, **context):
    source=ast.parse((ROOT/relative).read_text(encoding="utf-8"))
    nodes=[ast.ImportFrom(module="__future__",names=[ast.alias(name="annotations")],level=0)]
    nodes.extend(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in names)
    namespace={"pd":pd,"datetime":datetime,"sys":sys,**context}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),relative,"exec"),namespace)
    return namespace

class MigrationTests(unittest.TestCase):
    def test_stock_detail_does_not_send_market(self):
        sdk=Mock()
        def details(fields=None,status=None):
            return pd.DataFrame([{"symbol":"000001.SZ"}])
        sdk.get_stock_detail.side_effect=details
        sdk.get_market_min_data.return_value=pd.DataFrame([{"symbol":"000001.SZ","date":"20260102","close":1.0}])
        ns=functions("scripts/fetch_minute_data.py",{"fetch_minute_data"},_panda_data=sdk)
        ns["fetch_minute_data"]("20260101","20260102")
        self.assertNotIn("market",sdk.get_stock_detail.call_args.kwargs)

if __name__ == "__main__":
    unittest.main()
