import unittest
from hybrid_search_playground.core import search
class T(unittest.TestCase):
 def docs(self): return [{"id":"a","text":"red apple","vector":[1,0],"query_vector":[1,0]},{"id":"b","text":"blue","vector":[0,1],"query_vector":[1,0]}]
 def test_rank(self): self.assertEqual(search("apple",self.docs())[0]["id"],"a")
 def test_scores(self): self.assertIn("semantic",search("apple",self.docs())[0])
 def test_alpha(self): self.assertEqual(search("none",self.docs(),alpha=0)[0]["id"],"a")
 def test_limit(self): self.assertEqual(len(search("x",self.docs(),limit=1)),1)
 def test_missing(self):
  with self.assertRaises(ValueError): search("x",[{"id":"x","text":"x"}])
if __name__=="__main__": unittest.main()

