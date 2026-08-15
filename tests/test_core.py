import unittest
from semantic_index_doctor.core import diagnose
class T(unittest.TestCase):
 def test_ok(self): self.assertEqual(diagnose([{"id":"a","vector":[1,0]}],expected_dimension=2)["status"],"healthy")
 def test_dim(self): self.assertEqual(diagnose([{"id":"a","vector":[1]}],expected_dimension=2)["issues"][0]["issue"],"dimension")
 def test_dup(self): self.assertTrue(diagnose([{"id":"a","vector":[1]},{"id":"a","vector":[1]}],expected_dimension=1)["issues"])
 def test_zero(self): self.assertEqual(diagnose([{"id":"a","vector":[0]}],expected_dimension=1)["status"],"blocked")
 def test_nan(self): self.assertEqual(diagnose([{"id":"a","vector":[float("nan")]}],expected_dimension=1)["issues"][0]["issue"],"non_finite")
if __name__=="__main__": unittest.main()

