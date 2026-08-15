import unittest
from dataset_versioner.core import snapshot,diff
class T(unittest.TestCase):
 def test_stable(self): self.assertEqual(snapshot([{"id":1,"x":2}])["version"],snapshot([{"x":2,"id":1}])["version"])
 def test_add(self): self.assertEqual(diff([], [{"id":1}])["added"],["1"])
 def test_remove(self): self.assertEqual(diff([{"id":1}],[])["removed"],["1"])
 def test_change(self): self.assertEqual(diff([{"id":1,"x":1}],[{"id":1,"x":2}])["changed"],["1"])
 def test_duplicate(self):
  with self.assertRaises(ValueError): snapshot([{"id":1},{"id":1}])
if __name__=="__main__": unittest.main()

