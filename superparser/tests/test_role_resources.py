import unittest
from hashlib import sha1
from seman_parser.role_resources import rows,index,verify

class RoleResourcesTests(unittest.TestCase):
    def test_integrity(self):
        raw=b"abc"
        record={"name":"fixture","bytes":3,"git_blob_sha1":sha1(b"blob 3\0abc").hexdigest()}
        verify(raw,record)
        with self.assertRaises(ValueError):verify(b"abd",record)
    def test_native_rows_and_multiple_mappings(self):
        table=rows(b"license\nbn:1\twn:1\nbn:2\twn:1\n")
        self.assertEqual(index(table,1)["wn:1"],[["bn:1","wn:1"],["bn:2","wn:1"]])
