#!/usr/bin/env python
# ----------------------------------------------------------------------
#    Copyright (C) 2015 Christian Boltz <apparmor@cboltz.de>
#
#    This program is free software; you can redistribute it and/or
#    modify it under the terms of version 2 of the GNU General Public
#    License as published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
# ----------------------------------------------------------------------

import unittest
from collections import namedtuple
from common_test import AATest, setup_all_loops

from apparmor.rule.file import FileRule, FileRuleset
from apparmor.rule import BaseRule
from apparmor.common import AppArmorException, AppArmorBug
from apparmor.logparser import ReadLog
from apparmor.translations import init_translation
_ = init_translation()

exp = namedtuple('exp', ['audit', 'allow_keyword', 'deny', 'comment',
        'path', 'all_paths', 'perms', 'all_perms', 'exec_perms', 'target', 'all_targets', 'owner', 'file_keyword', 'leading_perms'])

# --- tests for single FileRule --- #

class FileTest(AATest):
    def _compare_obj(self, obj, expected):
        self.assertEqual(obj.allow_keyword, expected.allow_keyword)
        self.assertEqual(obj.audit, expected.audit)
        self.assertEqual(obj.deny, expected.deny)
        self.assertEqual(obj.comment, expected.comment)

        self._assertEqual_aare(obj.path, expected.path)
        self.assertEqual(obj.perms, expected.perms)
        self.assertEqual(obj.exec_perms, expected.exec_perms)
        self._assertEqual_aare(obj.target, expected.target)
        self.assertEqual(obj.owner, expected.owner)
        self.assertEqual(obj.file_keyword, expected.file_keyword)
        self.assertEqual(obj.leading_perms, expected.leading_perms)

        # Note: there's no all_ field for exec_perms, owner, file_keyword and leading_perms
        self.assertEqual(obj.all_paths, expected.all_paths)
        self.assertEqual(obj.all_perms, expected.all_perms)
        self.assertEqual(obj.all_targets, expected.all_targets)

    def _assertEqual_aare(self, obj, expected):
        if obj:
            self.assertEqual(obj.regex, expected)
        else:
            self.assertEqual(obj, expected)

class FileTestParse(FileTest):
    tests = [
        # FileRule object                             audit  allow  deny   comment    path              all_paths   perms           all?    exec_perms  target      all?    owner   file keyword    leading perms

        # bare file rules
        ('file,'                                , exp(False, False, False, '',        None,             True ,      None,           True,   None,       None,       True,   False,  False,          False       )),
        ('allow file,'                          , exp(False, True,  False, '',        None,             True ,      None,           True,   None,       None,       True,   False,  False,          False       )),
        ('audit deny owner file, # cmt'         , exp(True,  False, True,  ' # cmt',  None,             True ,      None,           True,   None,       None,       True,   True,   False,          False       )),

        # "normal" file rules
        ('/foo r,'                              , exp(False, False, False, '',        '/foo',           False,      {'r'},          False,  None,       None,       True,   False,  False,          False       )),
        ('file /foo rwix,'                      , exp(False, False, False, '',        '/foo',           False,      {'r', 'w'},     False,  'ix',       None,       True,   False,  True,           False       )),
        ('/foo Px -> bar,'                      , exp(False, False, False, '',        '/foo',           False,      set(),          False,  'Px',       'bar',      False,  False,  False,          False       )),
        ('@{PROC}/[a-z]** mr,'                  , exp(False, False, False, '',        '@{PROC}/[a-z]**',False,      {'r', 'm'},     False,  None,       None,       True,   False,  False,          False       )),

        ('audit /tmp/foo r,'                    , exp(True,  False, False, '',        '/tmp/foo',       False,      {'r'},          False,  None,       None,       True,   False,  False,          False       )),
        ('audit deny /tmp/foo r,'               , exp(True,  False, True,  '',        '/tmp/foo',       False,      {'r'},          False,  None,       None,       True,   False,  False,          False       )),
        ('audit deny /tmp/foo rx,'              , exp(True,  False, True,  '',        '/tmp/foo',       False,      {'r'},          False,  'x',        None,       True,   False,  False,          False       )),
        ('allow /tmp/foo ra,'                   , exp(False, True,  False, '',        '/tmp/foo',       False,      {'r', 'a'},     False,  None,       None,       True,   False,  False,          False       )),
        ('audit allow /tmp/foo ra,'             , exp(True,  True,  False, '',        '/tmp/foo',       False,      {'r', 'a'},     False,  None,       None,       True,   False,  False,          False       )),


        # file rules with leading permission
        ('r /foo,'                              , exp(False, False, False, '',        '/foo',           False,      {'r'},          False,  None,       None,       True,   False,  False,          True        )),
        ('file rwix /foo,'                      , exp(False, False, False, '',        '/foo',           False,      {'r', 'w'},     False,  'ix',       None,       True,   False,  True,           True        )),
        ('Px /foo -> bar,'                      , exp(False, False, False, '',        '/foo',           False,      set(),          False,  'Px',       'bar',      False,  False,  False,          True        )),
        ('mr @{PROC}/[a-z]**,'                  , exp(False, False, False, '',        '@{PROC}/[a-z]**',False,      {'r', 'm'},     False,  None,       None,       True,   False,  False,          True        )),

        ('audit r /tmp/foo,'                    , exp(True,  False, False, '',        '/tmp/foo',       False,      {'r'},          False,  None,       None,       True,   False,  False,          True        )),
        ('audit deny r /tmp/foo,'               , exp(True,  False, True,  '',        '/tmp/foo',       False,      {'r'},          False,  None,       None,       True,   False,  False,          True        )),
        ('allow ra /tmp/foo,'                   , exp(False, True,  False, '',        '/tmp/foo',       False,      {'r', 'a'},     False,  None,       None,       True,   False,  False,          True        )),
        ('audit allow ra /tmp/foo,'             , exp(True,  True,  False, '',        '/tmp/foo',       False,      {'r', 'a'},     False,  None,       None,       True,   False,  False,          True        )),

        # duplicated (but not conflicting) permissions
        ('/foo PxPxPxPxrwPx -> bar,'            , exp(False, False, False, '',        '/foo',           False,      {'r', 'w'},     False,  'Px',       'bar',      False,  False,  False,          False       )),
        ('/foo CixCixrwCix -> bar, '            , exp(False, False, False, '',        '/foo',           False,      {'r', 'w'},     False,  'Cix',      'bar',      False,  False,  False,          False       )),
    ]

    def _run_test(self, rawrule, expected):
        self.assertTrue(FileRule.match(rawrule))
        obj = FileRule.parse(rawrule)
        self.assertEqual(rawrule.strip(), obj.raw_rule)
        self._compare_obj(obj, expected)

class FileTestParseInvalid(FileTest):
    tests = [
        ('/foo x,'                      , AppArmorException),  # should be *x
        ('/foo raw,'                    , AppArmorException),  # r and a conflict
        ('deny /foo ix,'                , AppArmorException),  # endy only allows x, but not *x
        ('deny /foo Px,'                , AppArmorException),  # deny only allows x, but not *x
        ('deny /foo Pi,'                , AppArmorException),  # missing 'x', and P not allowed
        ('allow /foo x,'                , AppArmorException),  # should be *x
        ('/foo Pxrix,'                  , AppArmorException),  # exec mode conflict
        ('/foo PixUx,'                  , AppArmorException),  # exec mode conflict
        ('/foo PxUx,'                   , AppArmorException),  # exec mode conflict
        ('/foo PUxPix,'                 , AppArmorException),  # exec mode conflict
        ('/foo Pi,'                     , AppArmorException),  # missing 'x'
    ]

    def _run_test(self, rawrule, expected):
        self.assertTrue(FileRule.match(rawrule))  # the above invalid rules still match the main regex!
        with self.assertRaises(expected):
            FileRule.parse(rawrule)

class FileTestNonMatch(AATest):
    tests = [
        ('file /foo,'       , False ),
        ('file rw,'         , False ),
        ('file -> bar,'     , False ),
        ('file Px -> bar,'  , False ),
        ('/foo bar,'        , False ),
        ('dbus /foo,'       , False ),
    ]

    def _run_test(self, rawrule, expected):
        self.assertFalse(FileRule.match(rawrule))

class FileTestParseFromLog(FileTest):
    def test_file_from_log(self):
        parser = ReadLog('', '', '', '', '')
        event = 'Nov 11 07:33:07 myhost kernel: [50812.879558] type=1502 audit(1236774787.169:369): operation="inode_permission" requested_mask="::r" denied_mask="::r" fsuid=1000 name="/bin/dash" pid=13726 profile="/bin/foobar"'

        parsed_event = parser.parse_event(event)

        self.assertEqual(parsed_event, {
            'request_mask': '::r',
            'denied_mask': '::r',
            'error_code': 0,
            'magic_token': 0,
            'parent': 0,
            'profile': '/bin/foobar',
            'operation': 'inode_permission',
            'name': '/bin/dash',
            'name2': None,
            'resource': None,
            'info': None,
            'aamode': 'PERMITTING',
            'time': 1236774787,
            'active_hat': None,
            'pid': 13726,
            'task': 0,
            'attr': None,
        })

        #FileRule#     path,                 perms,                         exec_perms, target,         owner,  file_keyword,   leading_perms
        #obj = FileRule(parsed_event['name'], parsed_event['denied_mask'],   None,       FileRule.ALL,   False,  False,          False,         )
        obj = FileRule(parsed_event['name'], 'r',                           None,       FileRule.ALL,   False,  False,          False,         )
        # XXX handle things like '::r'
        # XXX split off exec perms?

        #              audit  allow  deny   comment    path              all_paths   perms           all?    exec_perms  target      all?    owner   file keyword    leading perms
        expected = exp(False, False, False, '',        '/bin/dash',      False,      {'r'},          False,  None,       None,       True,   False,  False,          False       )

        self._compare_obj(obj, expected)

        self.assertEqual(obj.get_raw(1), '  /bin/dash r,')

class FileFromInit(FileTest):
    tests = [

        #FileRule# path,            perms,  exec_perms, target,         owner,  file_keyword,   leading_perms
        (FileRule(  '/foo',         'rw',   None,       FileRule.ALL,   False,  False,          False,          audit=True,     deny=True   ),
                    #exp#   audit   allow   deny    comment     path            all_paths   perms           all?    exec_perms  target      all?    owner   file keyword    leading perms
                    exp(    True,   False,  True,   '',         '/foo',         False,      {'r', 'w'},     False,  None,       None,       True,   False,  False,          False       )),

        #FileRule# path,            perms,  exec_perms, target,         owner,  file_keyword,   leading_perms
        (FileRule(  '/foo',         None,   'Pix',      'bar_prof',     True,   True,           True,           allow_keyword=True          ),
                    #exp#   audit   allow   deny    comment     path            all_paths   perms           all?    exec_perms  target      all?    owner   file keyword    leading perms
                    exp(    False,  True,   False,  '',         '/foo',         False,      set(),          False,  'Pix',      'bar_prof', False,  True,   True,           True        )),

    ]

    def _run_test(self, obj, expected):
        self._compare_obj(obj, expected)

class InvalidFileInit(AATest):
    tests = [
        #FileRule# path,            perms,  exec_perms, target,         owner,  file_keyword,   leading_perms

        # empty fields
        (        (  '',             'rw',   'ix',       '/bar',         False,  False,          False   ), AppArmorBug),
          # OK   (  '/foo',         '',     'ix',       '/bar',         False,  False,          False   ), AppArmorBug),
        (        (  '/foo',         'rw',   '',         '/bar',         False,  False,          False   ), AppArmorBug),
        (        (  '/foo',         'rw',   'ix',       '',             False,  False,          False   ), AppArmorBug),

        # whitespace fields
        (        (  '   ',          'rw',   'ix',       '/bar',         False,  False,          False   ), AppArmorBug),
        (        (  '/foo',         '   ',  'ix',       '/bar',         False,  False,          False   ), AppArmorException),
        (        (  '/foo',         'rw',   '   ',      '/bar',         False,  False,          False   ), AppArmorBug),
        (        (  '/foo',         'rw',   'ix',       '   ',          False,  False,          False   ), AppArmorBug),

        # wrong type - dict()
        (        (  dict(),         'rw',   'ix',       '/bar',         False,  False,          False   ), AppArmorBug),
        (        (  '/foo',         dict(), 'ix',       '/bar',         False,  False,          False   ), AppArmorBug),
        (        (  '/foo',         'rw',   dict(),     '/bar',         False,  False,          False   ), AppArmorBug),
        (        (  '/foo',         'rw',   'ix',       dict(),         False,  False,          False   ), AppArmorBug),
        (        (  '/foo',         'rw',   'ix',       '/bar',         dict(), False,          False   ), AppArmorBug),
        (        (  '/foo',         'rw',   'ix',       '/bar',         False,  dict(),         False   ), AppArmorBug),
        (        (  '/foo',         'rw',   'ix',       '/bar',         False,  False,          dict()  ), AppArmorBug),


        # wrong type - None
        (        (  None,           'rw',   'ix',       '/bar',         False,  False,          False   ), AppArmorBug),
          # OK   (  '/foo',         None,   'ix',       '/bar',         False,  False,          False   ), AppArmorBug),
          # OK   (  '/foo',         'rw',   None,       '/bar',         False,  False,          False   ), AppArmorBug),
        (        (  '/foo',         'rw',   'ix',       None,           False,  False,          False   ), AppArmorBug),
        (        (  '/foo',         'rw',   'ix',       '/bar',         None,   False,          False   ), AppArmorBug),
        (        (  '/foo',         'rw',   'ix',       '/bar',         False,  None,           False   ), AppArmorBug),
        (        (  '/foo',         'rw',   'ix',       '/bar',         False,  False,          None    ), AppArmorBug),


        # misc
        (        (  '/foo',         'rwa',  'ix',       '/bar',         False,  False,          False   ), AppArmorException),  # 'r' and 'a' conflict
        (        (  '/foo',         None,   'rw',       '/bar',         False,  False,          False   ), AppArmorBug),        # file perms in exec perms parameter
        (        (  '/foo',         'ix',   None,       '/bar',         False,  False,          False   ), AppArmorBug),        # exec perms in file perms parameter
        (        (  'foo',          'rw',   'ix',       '/bar',         False,  False,          False   ), AppArmorException),  # path doesn't start with /
        (        (  '/foo',         'rb',   'ix',       '/bar',         False,  False,          False   ), AppArmorException),  # invalid file mode 'b' (str)
        (        (  '/foo',         {'b'},  'ix',       '/bar',         False,  False,          False   ), AppArmorBug),        # invalid file mode 'b' (str)
        (        (  '/foo',         'rw',   'ax',       '/bar',         False,  False,          False   ), AppArmorBug),        # invalid exec mode 'ax'
        (        (  '/foo',         'rw',   'x',        '/bar',         False,  False,          False   ), AppArmorException),  # plain 'x' is only allowed in deny rules
        (        (  FileRule.ALL,   FileRule.ALL, None, '/bar',         False,  False,          False   ), AppArmorBug),        # plain 'file,' doesn't allow exec target
    ]

    def _run_test(self, params, expected):
        with self.assertRaises(expected):
            FileRule(params[0], params[1], params[2], params[3], params[4], params[5], params[6])

    def test_missing_params_1(self):
        with self.assertRaises(TypeError):
            FileRule(  '/foo')

    def test_missing_params_2(self):
        with self.assertRaises(TypeError):
            FileRule(  '/foo',         'rw')

    def test_missing_params_3(self):
        with self.assertRaises(TypeError):
            FileRule(  '/foo',         'rw',   'ix')

    def test_missing_params_4(self):
        with self.assertRaises(TypeError):
            FileRule(  '/foo',         'rw',   'ix',       '/bar')

    def test_deny_ix(self):
        with self.assertRaises(AppArmorException):
            FileRule(  '/foo',         'rw',   'ix',       '/bar',         False,  False,       False,  deny=True)

class InvalidFileTest(AATest):
    def _check_invalid_rawrule(self, rawrule):
        obj = None
        self.assertFalse(FileRule.match(rawrule))
        with self.assertRaises(AppArmorException):
            obj = FileRule(FileRule.parse(rawrule))

        self.assertIsNone(obj, 'FileRule handed back an object unexpectedly')

    def test_invalid_file_missing_comma_1(self):
        self._check_invalid_rawrule('file')  # missing comma

    def test_invalid_non_FileRule(self):
        self._check_invalid_rawrule('signal,')  # not a file rule

class BrokenFileTest(AATest):
    def AASetup(self):
        #FileRule#          path,           perms,  exec_perms, target,         owner,  file_keyword,   leading_perms
        self.obj = FileRule('/foo',         'rw',   'ix',       '/bar',         False,  False,          False)

    def test_empty_data_1(self):
        self.obj.path = ''
        # no path set, and ALL not set
        with self.assertRaises(AppArmorBug):
            self.obj.get_clean(1)

    def test_empty_data_2(self):
        self.obj.perms = ''
        self.obj.exec_perms = ''
        # no perms or exec_perms set, and ALL not set
        with self.assertRaises(AppArmorBug):
            self.obj.get_clean(1)

    def test_empty_data_3(self):
        self.obj.target = ''
        # no target set, and ALL not set
        with self.assertRaises(AppArmorBug):
            self.obj.get_clean(1)

    def test_unexpected_all_1(self):
        self.obj.all_paths = FileRule.ALL
        # all_paths and all_perms must be in sync
        with self.assertRaises(AppArmorBug):
            self.obj.get_clean(1)

    def test_unexpected_all_2(self):
        self.obj.all_perms = FileRule.ALL
        # all_paths and all_perms must be in sync
        with self.assertRaises(AppArmorBug):
            self.obj.get_clean(1)



class WriteFileTest(AATest):
    def _run_test(self, rawrule, expected):
       self.assertTrue(FileRule.match(rawrule), 'FileRule.match() failed')
       obj = FileRule.parse(rawrule)
       clean = obj.get_clean()
       raw = obj.get_raw()

       self.assertEqual(expected.strip(), clean, 'unexpected clean rule')
       self.assertEqual(rawrule.strip(), raw, 'unexpected raw rule')

    tests = [
        #  raw rule                                                           clean rule
        ('file,'                                                            , 'file,'),
        ('              file        ,  # foo        '                       , 'file, # foo'),
        ('    audit     file /foo r,'                                       , 'audit file /foo r,'),
        ('    audit     file /foo  lwr,'                                    , 'audit file /foo rwl,'),
        ('    audit     file /foo Pxrm -> bar,'                             , 'audit file /foo mrPx -> bar,'),
        ('    deny      file /foo r,'                                       , 'deny file /foo r,'),
        ('    deny      file /foo  wr,'                                     , 'deny file /foo rw,'),
        ('    allow     file /foo Pxrm -> bar,'                             , 'allow file /foo mrPx -> bar,'),
        ('    deny    owner  /foo r,'                                       , 'deny owner /foo r,'),
        ('    deny    owner  /foo  wr,'                                     , 'deny owner /foo rw,'),
        ('    allow   owner  /foo Pxrm -> bar,'                             , 'allow owner /foo mrPx -> bar,'),
        ('                   /foo r,'                                       , '/foo r,'),
        ('                   /foo  lwr,'                                    , '/foo rwl,'),
        ('                   /foo Pxrm -> bar,'                             , '/foo mrPx -> bar,'),

        # with leading permissions
        ('    audit     file r      /foo,'                                  , 'audit file r /foo,'),
        ('    audit     file lwr    /foo,'                                  , 'audit file rwl /foo,'),
        ('    audit     file Pxrm   /foo -> bar,'                           , 'audit file mrPx /foo -> bar,'),
        ('    deny      file r      /foo,'                                  , 'deny file r /foo,'),
        ('    deny      file wr     /foo  ,'                                , 'deny file rw /foo,'),
        ('    allow     file Pxmr   /foo -> bar,'                           , 'allow file mrPx /foo -> bar,'),
        ('    deny    owner  r      /foo ,'                                 , 'deny owner r /foo,'),
        ('    deny    owner  wr     /foo  ,'                                , 'deny owner rw /foo,'),
        ('    allow   owner  Pxrm   /foo -> bar,'                           , 'allow owner mrPx /foo -> bar,'),
        ('                   r      /foo ,'                                 , 'r /foo,'),
        ('                   klwr   /foo  ,'                                , 'rwlk /foo,'),
        ('                   Pxrm   /foo -> bar,'                           , 'mrPx /foo -> bar,'),
  ]

    def test_write_manually_1(self):
       #FileRule#      path,           perms,  exec_perms, target,         owner,  file_keyword,   leading_perms
       obj = FileRule( '/foo',         'rw',   'Px',       '/bar',         False,  True,           False,       allow_keyword=True)

       expected = '    allow file /foo rwPx -> /bar,'

       self.assertEqual(expected, obj.get_clean(2), 'unexpected clean rule')
       self.assertEqual(expected, obj.get_raw(2), 'unexpected raw rule')

    def test_write_manually_2(self):
       #FileRule#      path,           perms,  exec_perms, target,         owner,  file_keyword,   leading_perms
       obj = FileRule( '/foo',         'rw',   'x',        FileRule.ALL,   True,   False,          True,        deny=True)

       expected = '    deny owner rwx /foo,'

       self.assertEqual(expected, obj.get_clean(2), 'unexpected clean rule')
       self.assertEqual(expected, obj.get_raw(2), 'unexpected raw rule')


class FileCoveredTest(AATest):
    def _run_test(self, param, expected):
        obj = FileRule.parse(self.rule)
        check_obj = FileRule.parse(param)

        self.assertTrue(FileRule.match(param))

        self.assertEqual(obj.is_equal(check_obj), expected[0], 'Mismatch in is_equal, expected %s' % expected[0])
        self.assertEqual(obj.is_equal(check_obj, True), expected[1], 'Mismatch in is_equal/strict, expected %s' % expected[1])

        self.assertEqual(obj.is_covered(check_obj), expected[2], 'Mismatch in is_covered, expected %s' % expected[2])
        self.assertEqual(obj.is_covered(check_obj, True, True), expected[3], 'Mismatch in is_covered/exact, expected %s' % expected[3])

class FileCoveredTest_01(FileCoveredTest):
    rule = 'file /foo r,'

    tests = [
        #   rule                                            equal     strict equal    covered     covered exact
        ('file /foo r,'                                 , [ True    , True          , True      , True      ]),
        ('file /foo r ,'                                , [ True    , False         , True      , True      ]),
        ('allow file /foo r,'                           , [ True    , False         , True      , True      ]),
        ('allow /foo r, # comment'                      , [ True    , False         , True      , True      ]),
        ('allow owner /foo r,'                          , [ False   , False         , True      , True      ]),
        ('/foo r -> bar,'                               , [ False   , False         , True      , True      ]),
        ('file r /foo,'                                 , [ True    , False         , True      , True      ]),
        ('allow file r /foo,'                           , [ True    , False         , True      , True      ]),
        ('allow r /foo, # comment'                      , [ True    , False         , True      , True      ]),
        ('allow owner r /foo,'                          , [ False   , False         , True      , True      ]),
        ('r /foo -> bar,'                               , [ False   , False         , True      , True      ]),
        ('file,'                                        , [ False   , False         , False     , False     ]),
        ('file /foo w,'                                 , [ False   , False         , False     , False     ]),
        ('file /foo rw,'                                , [ False   , False         , False     , False     ]),
        ('file /bar r,'                                 , [ False   , False         , False     , False     ]),
        ('audit /foo r,'                                , [ False   , False         , False     , False     ]),
        ('audit file,'                                  , [ False   , False         , False     , False     ]),
        ('audit deny /foo r,'                           , [ False   , False         , False     , False     ]),
        ('deny file /foo r,'                            , [ False   , False         , False     , False     ]),
        ('/foo rPx,'                                    , [ False   , False         , False     , False     ]),
        ('/foo Pxr,'                                    , [ False   , False         , False     , False     ]),
        ('/foo Px,'                                     , [ False   , False         , False     , False     ]),
        ('/foo ix,'                                     , [ False   , False         , False     , False     ]),
        ('/foo ix -> bar,'                              , [ False   , False         , False     , False     ]),
        ('/foo rPx -> bar,'                             , [ False   , False         , False     , False     ]),
    ]

class FileCoveredTest_02(FileCoveredTest):
    rule = 'audit /foo r,'

    tests = [
        #   rule                                            equal     strict equal    covered     covered exact
        ('file /foo r,'                                 , [ False   , False         , True      , False     ]),
        ('allow file /foo r,'                           , [ False   , False         , True      , False     ]),
        ('allow /foo r, # comment'                      , [ False   , False         , True      , False     ]),
        ('allow owner /foo r,'                          , [ False   , False         , True      , False     ]),
        ('/foo r -> bar,'                               , [ False   , False         , True      , False     ]),
        ('file r /foo,'                                 , [ False   , False         , True      , False     ]),
        ('allow file r /foo,'                           , [ False   , False         , True      , False     ]),
        ('allow r /foo, # comment'                      , [ False   , False         , True      , False     ]),
        ('allow owner r /foo,'                          , [ False   , False         , True      , False     ]),
        ('r /foo -> bar,'                               , [ False   , False         , True      , False     ]), # XXX exact
        ('file,'                                        , [ False   , False         , False     , False     ]),
        ('file /foo w,'                                 , [ False   , False         , False     , False     ]),
        ('file /foo rw,'                                , [ False   , False         , False     , False     ]),
        ('file /bar r,'                                 , [ False   , False         , False     , False     ]),
        ('audit /foo r,'                                , [ True    , True          , True      , True      ]),
        ('audit file,'                                  , [ False   , False         , False     , False     ]),
        ('audit deny /foo r,'                           , [ False   , False         , False     , False     ]),
        ('deny file /foo r,'                            , [ False   , False         , False     , False     ]),
        ('/foo rPx,'                                    , [ False   , False         , False     , False     ]),
        ('/foo Pxr,'                                    , [ False   , False         , False     , False     ]),
        ('/foo Px,'                                     , [ False   , False         , False     , False     ]),
        ('/foo ix,'                                     , [ False   , False         , False     , False     ]),
        ('/foo ix -> bar,'                              , [ False   , False         , False     , False     ]),
        ('/foo rPx -> bar,'                             , [ False   , False         , False     , False     ]),
    ]

class FileCoveredTest_03(FileCoveredTest):
    rule = '/foo mrwPx,'

    tests = [
        #   rule                                            equal     strict equal    covered     covered exact
        ('file /foo r,'                                 , [ False   , False         , True      , True      ]),
        ('allow file /foo r,'                           , [ False   , False         , True      , True      ]),
        ('allow /foo r, # comment'                      , [ False   , False         , True      , True      ]),
        ('allow owner /foo r,'                          , [ False   , False         , True      , True      ]),
        ('/foo r -> bar,'                               , [ False   , False         , True      , True      ]),
        ('file r /foo,'                                 , [ False   , False         , True      , True      ]),
        ('allow file r /foo,'                           , [ False   , False         , True      , True      ]),
        ('allow r /foo, # comment'                      , [ False   , False         , True      , True      ]),
        ('allow owner r /foo,'                          , [ False   , False         , True      , True      ]),
        ('r /foo -> bar,'                               , [ False   , False         , True      , True      ]),
        ('file,'                                        , [ False   , False         , False     , False     ]),
        ('file /foo w,'                                 , [ False   , False         , True      , True      ]),
        ('file /foo rw,'                                , [ False   , False         , True      , True      ]),
        ('file /bar r,'                                 , [ False   , False         , False     , False     ]),
        ('audit /foo r,'                                , [ False   , False         , False     , False     ]),
        ('audit file,'                                  , [ False   , False         , False     , False     ]),
        ('audit deny /foo r,'                           , [ False   , False         , False     , False     ]),
        ('deny file /foo r,'                            , [ False   , False         , False     , False     ]),
        ('/foo mrwPx,'                                  , [ True    , True          , True      , True      ]),
        ('/foo wPxrm,'                                  , [ True    , False         , True      , True      ]),
        ('/foo rm,'                                     , [ False   , False         , True      , True      ]),
        ('/foo Px,'                                     , [ False   , False         , True      , True      ]),
        ('/foo ix,'                                     , [ False   , False         , False     , False     ]),
        ('/foo ix -> bar,'                              , [ False   , False         , False     , False     ]),
        ('/foo mrwPx -> bar,'                           , [ False   , False         , False     , False     ]),
    ]

class FileCoveredTest_04(FileCoveredTest):
    rule = '/foo mrwPx -> bar,'

    tests = [
        #   rule                                            equal     strict equal    covered     covered exact
        ('file /foo r,'                                 , [ False   , False         , True      , True      ]),
        ('allow file /foo r,'                           , [ False   , False         , True      , True      ]),
        ('allow /foo r, # comment'                      , [ False   , False         , True      , True      ]),
        ('allow owner /foo r,'                          , [ False   , False         , True      , True      ]),
        ('/foo r -> bar,'                               , [ False   , False         , True      , True      ]),
        ('file r /foo,'                                 , [ False   , False         , True      , True      ]),
        ('allow file r /foo,'                           , [ False   , False         , True      , True      ]),
        ('allow r /foo, # comment'                      , [ False   , False         , True      , True      ]),
        ('allow owner r /foo,'                          , [ False   , False         , True      , True      ]),
        ('r /foo -> bar,'                               , [ False   , False         , True      , True      ]),
        ('file,'                                        , [ False   , False         , False     , False     ]),
        ('file /foo w,'                                 , [ False   , False         , True      , True      ]),
        ('file /foo rw,'                                , [ False   , False         , True      , True      ]),
        ('file /bar r,'                                 , [ False   , False         , False     , False     ]),
        ('audit /foo r,'                                , [ False   , False         , False     , False     ]),
        ('audit file,'                                  , [ False   , False         , False     , False     ]),
        ('audit deny /foo r,'                           , [ False   , False         , False     , False     ]),
        ('deny file /foo r,'                            , [ False   , False         , False     , False     ]),
        ('/foo mrwPx,'                                  , [ False   , False         , False     , False     ]),
        ('/foo wPxrm,'                                  , [ False   , False         , False     , False     ]),
        ('/foo rm,'                                     , [ False   , False         , True      , True      ]),
        ('/foo Px,'                                     , [ False   , False         , False     , False     ]),
        ('/foo ix,'                                     , [ False   , False         , False     , False     ]),
        ('/foo ix -> bar,'                              , [ False   , False         , False     , False     ]),
        ('/foo mrwPx -> bar,'                           , [ True    , True          , True      , True      ]),
    ]

class FileCoveredTest_05(FileCoveredTest):
    rule = 'file,'

    tests = [
        #   rule                                            equal     strict equal    covered     covered exact
        ('file /foo r,'                                 , [ False   , False         , True      , True      ]),
        ('allow file /foo r,'                           , [ False   , False         , True      , True      ]),
        ('allow /foo r, # comment'                      , [ False   , False         , True      , True      ]),
        ('allow owner /foo r,'                          , [ False   , False         , True      , True      ]),
        ('/foo r -> bar,'                               , [ False   , False         , True      , True      ]),
        ('file r /foo,'                                 , [ False   , False         , True      , True      ]),
        ('allow file r /foo,'                           , [ False   , False         , True      , True      ]),
        ('allow r /foo, # comment'                      , [ False   , False         , True      , True      ]),
        ('allow owner r /foo,'                          , [ False   , False         , True      , True      ]),
        ('r /foo -> bar,'                               , [ False   , False         , True      , True      ]),
        ('file,'                                        , [ True    , True          , True      , True      ]),
        ('file /foo w,'                                 , [ False   , False         , True      , True      ]),
        ('file /foo rw,'                                , [ False   , False         , True      , True      ]),
        ('file /bar r,'                                 , [ False   , False         , True      , True      ]),
        ('audit /foo r,'                                , [ False   , False         , False     , False     ]),
        ('audit file,'                                  , [ False   , False         , False     , False     ]),
        ('audit deny /foo r,'                           , [ False   , False         , False     , False     ]),
        ('deny file /foo r,'                            , [ False   , False         , False     , False     ]),
        ('/foo mrwPx,'                                  , [ False   , False         , False     , False     ]),
        ('/foo wPxrm,'                                  , [ False   , False         , False     , False     ]),
        ('/foo rm,'                                     , [ False   , False         , True      , True      ]),
        ('/foo Px,'                                     , [ False   , False         , False     , False     ]),
        ('/foo ix,'                                     , [ False   , False         , False     , False     ]),
        ('/foo ix -> bar,'                              , [ False   , False         , False     , False     ]),
        ('/foo mrwPx -> bar,'                           , [ False   , False         , False     , False     ]),
    ]

class FileCoveredTest_ManualOrInvalid(AATest):
    def AASetup(self):
        #FileRule#                 path,           perms,  exec_perms, target,         owner,  file_keyword,   leading_perms
        self.obj       = FileRule( '/foo',         'rw',   'ix',       '/bar',         False,  False,          False)
        self.testobj   = FileRule( '/foo',         'rw',   'ix',       '/bar',         False,  False,          False)

    def test_covered_owner_1(self):
        # testobj with 'owner'
        self.testobj   = FileRule( '/foo',         'rw',   'ix',       '/bar',         True,   False,          False)
        self.assertTrue(self.obj.is_covered(self.testobj))

    def test_covered_owner_2(self):
        # obj with 'owner'
        self.obj       = FileRule( '/foo',         'rw',   'ix',       '/bar',         True,   False,          False)
        self.assertFalse(self.obj.is_covered(self.testobj))

    def test_equal_all_perms(self):
        self.testobj.all_perms = True  # that makes testobj invalid, but that's the only way to survive the 'perms' comparison
        self.assertFalse(self.obj.is_equal(self.testobj))

    def test_equal_file_keyword(self):
        # testobj with file_keyword
        self.testobj   = FileRule( '/foo',         'rw',   'ix',       '/bar',         False,  True,           False)
        self.assertTrue(self.obj.is_equal(self.testobj, strict=False))
        self.assertFalse(self.obj.is_equal(self.testobj, strict=True))

    def test_equal_file_leading_perms(self):
        # testobj with leading_perms
        self.testobj   = FileRule( '/foo',         'rw',   'ix',       '/bar',         False,  False,          True)
        self.assertTrue(self.obj.is_equal(self.testobj, strict=False))
        self.assertFalse(self.obj.is_equal(self.testobj, strict=True))

    def test_borked_obj_is_covered_1(self):
        self.testobj.path = ''

        with self.assertRaises(AppArmorBug):
            self.obj.is_covered(self.testobj)

    def test_borked_obj_is_covered_2(self):
        self.testobj.perms = set()
        self.testobj.exec_perms = ''

        with self.assertRaises(AppArmorBug):
            self.obj.is_covered(self.testobj)

    def test_borked_obj_is_covered_3(self):
        self.testobj.target = ''

        with self.assertRaises(AppArmorBug):
            self.obj.is_covered(self.testobj)

    def test_invalid_is_covered(self):
        obj = FileRule.parse('file,')

        testobj = BaseRule()  # different type

        with self.assertRaises(AppArmorBug):
            obj.is_covered(testobj)

    def test_invalid_is_equal(self):
        obj = FileRule.parse('file,')

        testobj = BaseRule()  # different type

        with self.assertRaises(AppArmorBug):
            obj.is_equal(testobj)

#class FileLogprofHeaderTest(AATest):
#    tests = [
#        ('file,',                        [                               _('Access mode'), _('ALL'),    _('Bus'), _('ALL'),    _('Path'), _('ALL'), _('Name'), _('ALL'),    _('Interface'), _('ALL'),  _('Member'), _('ALL'), _('Peer exec_perms'), _('ALL'),   _('Peer label'), _('ALL')]),
#        ('file (send receive),',         [                               _('Access mode'), 'receive send', _('Bus'), _('ALL'), _('Path'), _('ALL'), _('Name'), _('ALL'),    _('Interface'), _('ALL'),  _('Member'), _('ALL'), _('Peer exec_perms'), _('ALL'),   _('Peer label'), _('ALL')]),
#        ('file send bus=session,',       [                               _('Access mode'), 'send',      _('Bus'), 'session',   _('Path'), _('ALL'), _('Name'), _('ALL'),    _('Interface'), _('ALL'),  _('Member'), _('ALL'), _('Peer exec_perms'), _('ALL'),   _('Peer label'), _('ALL')]),
#        ('deny file,',                   [_('Qualifier'), 'deny',        _('Access mode'), _('ALL'),    _('Bus'), _('ALL'),    _('Path'), _('ALL'), _('Name'), _('ALL'),    _('Interface'), _('ALL'),  _('Member'), _('ALL'), _('Peer exec_perms'), _('ALL'),   _('Peer label'), _('ALL')]),
#        ('allow file send,',             [_('Qualifier'), 'allow',       _('Access mode'), 'send',      _('Bus'), _('ALL'),    _('Path'), _('ALL'), _('Name'), _('ALL'),    _('Interface'), _('ALL'),  _('Member'), _('ALL'), _('Peer exec_perms'), _('ALL'),   _('Peer label'), _('ALL')]),
#        ('audit file send bus=session,', [_('Qualifier'), 'audit',       _('Access mode'), 'send',      _('Bus'), 'session',   _('Path'), _('ALL'), _('Name'), _('ALL'),    _('Interface'), _('ALL'),  _('Member'), _('ALL'), _('Peer exec_perms'), _('ALL'),   _('Peer label'), _('ALL')]),
#        ('audit deny file send,',        [_('Qualifier'), 'audit deny',  _('Access mode'), 'send',      _('Bus'), _('ALL'),    _('Path'), _('ALL'), _('Name'), _('ALL'),    _('Interface'), _('ALL'),  _('Member'), _('ALL'), _('Peer exec_perms'), _('ALL'),   _('Peer label'), _('ALL')]),
#        ('file bind exec_perms=bind.exec_perms,',    [                               _('Access mode'), 'bind',      _('Bus'), _('ALL'),    _('Path'), _('ALL'), _('Name'), 'bind.exec_perms', _('Interface'), _('ALL'),  _('Member'), _('ALL'), _('Peer exec_perms'), _('ALL'),   _('Peer label'), _('ALL')]),
#        ('file send bus=session path=/path target=aa.test owner=ExMbr peer=(exec_perms=(peer.exec_perms)),',
#                                         [                               _('Access mode'), 'send',      _('Bus'), 'session',   _('Path'), '/path',  _('Name'), _('ALL'),    _('Interface'), 'aa.test', _('Member'), 'ExMbr',  _('Peer exec_perms'), 'peer.exec_perms',_('Peer label'), _('ALL')]),
#        ('file send peer=(label=foo),',  [                               _('Access mode'), 'send',      _('Bus'), _('ALL'),    _('Path'), _('ALL'), _('Name'), _('ALL'),    _('Interface'), _('ALL'),  _('Member'), _('ALL'), _('Peer exec_perms'), _('ALL'),   _('Peer label'), 'foo'   ]),
#   ]
#
#    def _run_test(self, params, expected):
#        obj = FileRule._parse(params)
#        self.assertEqual(obj.logprof_header(), expected)

## --- tests for FileRuleset --- #

class FileRulesTest(AATest):
    def test_empty_ruleset(self):
        ruleset = FileRuleset()
        ruleset_2 = FileRuleset()
        self.assertEqual([], ruleset.get_raw(2))
        self.assertEqual([], ruleset.get_clean(2))
        self.assertEqual([], ruleset_2.get_raw(2))
        self.assertEqual([], ruleset_2.get_clean(2))

    def test_ruleset_1(self):
        ruleset = FileRuleset()
        rules = [
            '         file             ,        ',
            '   file /foo rw,',
            '  file /bar r,',
        ]

        expected_raw = [
            'file             ,',
            'file /foo rw,',
            'file /bar r,',
            '',
        ]

        expected_clean = [
            'file /bar r,',
            'file /foo rw,',
            'file,',
            '',
        ]

        for rule in rules:
            ruleset.add(FileRule.parse(rule))

        self.assertEqual(expected_raw, ruleset.get_raw())
        self.assertEqual(expected_clean, ruleset.get_clean())

    def test_ruleset_2(self):
        ruleset = FileRuleset()
        rules = [
            '/foo Px,',
            '/bar    Cx    ->     bar_child ,',
            'deny /asdf w,',
        ]

        expected_raw = [
            '  /foo Px,',
            '  /bar    Cx    ->     bar_child ,',
            '  deny /asdf w,',
             '',
        ]

        expected_clean = [
            '  deny /asdf w,',
            '',
            '  /bar Cx -> bar_child,',
            '  /foo Px,',
             '',
        ]

        for rule in rules:
            ruleset.add(FileRule.parse(rule))

        self.assertEqual(expected_raw, ruleset.get_raw(1))
        self.assertEqual(expected_clean, ruleset.get_clean(1))


#class FileGlobTest(AATest):
# XXX not (really) implemented yet
#    def setUp(self):
#        self.maxDiff = None
#        self.ruleset = FileRuleset()
# 
#    def test_glob_1(self):
#        self.assertEqual(self.ruleset.get_glob('file send,'), 'file,')
# 
#    # not supported or used yet
#    # def test_glob_2(self):
#    #     self.assertEqual(self.ruleset.get_glob('file send raw,'), 'file send,')
# 
#    def test_glob_ext(self):
#        with self.assertRaises(NotImplementedError):
#            # get_glob_ext is not available for file rules
#            self.ruleset.get_glob_ext('file send peer=(label=foo),')

#class FileDeleteTest(AATest):
#    pass

setup_all_loops(__name__)
if __name__ == '__main__':
    unittest.main(verbosity=2)
