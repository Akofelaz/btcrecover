#!/usr/bin/python

# test-btcr.py -- unit tests for btcrecovery.py
# Copyright (C) 2014 Christopher Gurnee
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# version 2 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License version 2 for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

# If you find this program helpful, please consider a small donation
# donation to the developer at the following Bitcoin address:
#
#           17LGpN2z62zp7RS825jXwYtE7zZ19Mxxu8
#
#                      Thank You!

# (all futures as of 2.6 and 2.7 except unicode_literals)
from __future__ import print_function, absolute_import, division, \
                       generators, nested_scopes, with_statement

import btcrecover, unittest, cStringIO, StringIO, os, os.path, \
       cPickle, tempfile, shutil, filecmp

wallet_dir = os.path.join(os.path.dirname(__file__), "test-wallets")


class StringIONonClosing(StringIO.StringIO):
    def close(self): pass


class GeneratorTester(unittest.TestCase):

    # tokenlist == a list of lines (w/o "\n") which will become the tokenlist file
    # expected_passwords == a list of passwords which should be produced from the tokenlist
    # extra_cmd_line == a single string of additional command-line options
    # extra_kwds == additional StringIO objects to act as file stand-ins
    def do_generator_test(self, tokenlist, expected_passwords, extra_cmd_line = "", **extra_kwds):
        assert isinstance(tokenlist, list)
        assert isinstance(expected_passwords, list)
        test_passwordlist = extra_kwds.get("test_passwordlist")
        if test_passwordlist: del extra_kwds["test_passwordlist"]
        btcrecover.parse_arguments(
            ("--tokenlist __funccall --listpass "+extra_cmd_line).split(),
            tokenlist = cStringIO.StringIO("\n".join(tokenlist)),
            **extra_kwds)
        self.assertEqual(list(btcrecover.password_generator()), expected_passwords)
        if test_passwordlist:
            btcrecover.parse_arguments(
                ("--passwordlist __funccall --listpass "+extra_cmd_line).split(),
                passwordlist = cStringIO.StringIO("\n".join(tokenlist)),
                **extra_kwds)
            self.assertEqual(list(btcrecover.password_generator()), expected_passwords)

    # tokenlist == a list of lines (w/o "\n") which will become the tokenlist file
    # expected_error == a (partial) error message that should be produced from the tokenlist
    # extra_cmd_line == a single string of additional command-line options
    # extra_kwds == additional StringIO objects to act as file stand-ins
    def expect_syntax_failure(self, tokenlist, expected_error, extra_cmd_line = "", **extra_kwds):
        assert isinstance(tokenlist, list)
        with self.assertRaises(SystemExit) as cm:
            btcrecover.parse_arguments(
                ("--tokenlist __funccall --listpass "+extra_cmd_line).split(),
                tokenlist = cStringIO.StringIO("\n".join(tokenlist)),
                **extra_kwds)
        self.assertIn(expected_error, cm.exception.code)


class Test01Basics(GeneratorTester):

    def test_alternate(self):
        self.do_generator_test(["one", "two"], ["one", "two", "twoone", "onetwo"])

    def test_mutex(self):
        self.do_generator_test(["one two three"], ["one", "two", "three"])

    def test_require(self):
        self.do_generator_test(["one", "+ two", "+ three"],
            ["threetwo", "twothree", "threetwoone", "threeonetwo",
            "twothreeone", "twoonethree", "onethreetwo", "onetwothree"])

    def test_token_counts_min_0(self):
        self.do_generator_test(["one"], ["", "one"], "--min-tokens 0")
    def test_token_counts_min_2(self):
        self.do_generator_test(["one", "two", "three"],
            ["twoone", "onetwo", "threeone", "onethree", "threetwo", "twothree", "threetwoone",
            "threeonetwo", "twothreeone", "twoonethree", "onethreetwo", "onetwothree"],
            "--min-tokens 2")
    def test_token_counts_max_2(self):
        self.do_generator_test(["one", "two", "three"],
            ["one", "two", "twoone", "onetwo", "three", "threeone", "onethree", "threetwo", "twothree"],
            "--max-tokens 2")
    def test_token_counts_min_max_2(self):
        self.do_generator_test(["one", "two", "three"],
            ["twoone", "onetwo", "threeone", "onethree", "threetwo", "twothree"],
            "--min-tokens 2 --max-tokens 2")

    def test_z_all(self):
        self.do_generator_test(["1", "2 3", "+ 4 5"], map(str, [
            4,41,14,42,24,421,412,241,214,142,124,43,34,431,413,341,314,143,134,
            5,51,15,52,25,521,512,251,215,152,125,53,35,531,513,351,315,153,135]))


class Test02Anchors(GeneratorTester):

    def test_begin(self):
        self.do_generator_test(["^one", "^two", "three"],
            ["one", "two", "three", "onethree", "twothree"])

    def test_end(self):
        self.do_generator_test(["one$", "two$", "three"],
            ["one", "two", "three", "threeone", "threetwo"])

    def test_begin_and_end(self):
        self.expect_syntax_failure(["^one$"], "token on line 1 is anchored with both ^ at the beginning and $ at the end")

    def test_positional(self):
        self.do_generator_test(["one", "^2$two", "^3$three"], ["one", "onetwo", "onetwothree"])

    def test_positional_0len(self):
        self.do_generator_test(["+ ^1$", "^2$two"], ["", "two"])

    def test_positional_invalid(self):
        self.expect_syntax_failure(["^0$zero"], "anchor position of token on line 1 must be 1 or greater")

    def test_middle(self):
        self.do_generator_test(["^one", "^2,2$two", "^,3$three", "^,$four", "five$"],
            ["one", "five", "onefive", "onetwofive", "onethreefive", "onetwothreefive", "onefourfive",
            "onetwofourfive", "onefourthreefive", "onethreefourfive", "onetwothreefourfive"])

    def test_middle_0len(self):
        self.do_generator_test(["one", "+ ^,$", "^3$three"], ["onethree"])

    def test_middle_invalid_begin(self):
        self.expect_syntax_failure(["^1,$one"],  "anchor range of token on line 1 must begin with 2 or greater")
    def test_middle_invalid_range(self):
        self.expect_syntax_failure(["^3,2$one"], "anchor range of token on line 1 is invalid")


class Test03WildCards(GeneratorTester):

    def test_basics_1(self):
        self.do_generator_test(["%d"], map(str, xrange(10)))
    def test_basics_2(self):
        self.do_generator_test(["%dtest"], [str(i)+"test" for i in xrange(10)])
    def test_basics_3(self):
        self.do_generator_test(["te%dst"], ["te"+str(i)+"st" for i in xrange(10)])
    def test_basics_4(self):
        self.do_generator_test(["test%d"], ["test"+str(i) for i in xrange(10)])

    def test_invalid_nocust(self):
        self.expect_syntax_failure(["%c"],    "invalid wildcard")
    def test_invalid_nocust_cap(self):
        self.expect_syntax_failure(["%C"],    "invalid wildcard")
    def test_invalid_notype(self):
        self.expect_syntax_failure(["test%"], "invalid wildcard")

    def test_multiple(self):
        self.do_generator_test(["%d%d"], ["{:02}".format(i) for i in xrange(100)])

    def test_length_2(self):
        self.do_generator_test(["%2d"],  ["{:02}".format(i) for i in xrange(100)])
    def test_length_range(self):
        self.do_generator_test(["%0,2d"],
            [""] +
            map(str, xrange(10)) +
            ["{:02}".format(i) for i in xrange(100)])

    def test_length_invalid_range(self):
        self.expect_syntax_failure(["%2,1d"], "on line 1: min wildcard length (2) > max length (1)")
    def test_invalid_length_1(self):
        self.expect_syntax_failure(["%2,d"],  "invalid wildcard")
    def test_invalid_length_2(self):
        self.expect_syntax_failure(["%,2d"],  "invalid wildcard")

    def test_case_lower(self):
        self.do_generator_test(["%a"], map(chr, xrange(ord("a"), ord("z")+1)))
    def test_case_upper(self):
        self.do_generator_test(["%A"], map(chr, xrange(ord("A"), ord("Z")+1)))
    def test_case_insensitive_1(self):
        self.do_generator_test(["%ia"],
            map(chr, xrange(ord("a"), ord("z")+1)) + map(chr, xrange(ord("A"), ord("Z")+1)))
    def test_case_insensitive_2(self):
        self.do_generator_test(["%iA"],
            map(chr, xrange(ord("A"), ord("Z")+1)) + map(chr, xrange(ord("a"), ord("z")+1)))

    def test_custom(self):
        self.do_generator_test(["%c"],  ["a", "b", "c", "D", "2"], "--custom-wild a-cD2")
    def test_custom_upper(self):
        self.do_generator_test(["%C"],  ["A", "B", "C", "D", "2"], "--custom-wild a-cD2")
    def test_custom_insensitive_1(self):
        self.do_generator_test(["%ic"], ["a", "b", "c", "D", "2", "A", "B", "C", "d"],
            "--custom-wild a-cD2 -d")
    def test_custom_insensitive_2(self):
        self.do_generator_test(["%iC"], ["A", "B", "C", "d", "2", "a", "b", "c", "D"],
            "--custom-wild a-cD2 -d")

    def test_set(self):
        self.do_generator_test(["%[abcc-]"], ["a", "b", "c", "-"], "-d")
    def test_set_insensitive(self):
        self.do_generator_test(["%i[abcc-]"], ["a", "b", "c", "-", "A", "B", "C"], "-d")
    def test_noset(self):
        self.do_generator_test(["%%[not-a-range]"], ["%[not-a-range]"])

    def test_range_1(self):
        self.do_generator_test(["%[1dc-f]"],  ["1", "d", "c", "e", "f"], "-d")
    def test_range_2(self):
        self.do_generator_test(["%[a-c-e]"], ["a", "b", "c", "-", "e"])
    def test_range_insensitive(self):
        self.do_generator_test(["%i[1dc-f]"], ["1", "d", "c", "e", "f", "D", "C", "E", "F"], "-d")

    def test_range_invalid(self):
        self.expect_syntax_failure(["%[c-a]"],  "first character in wildcard range 'c' > last 'a'")

    def test_contracting_1(self):
        self.do_generator_test(["a%0,2-bcd"], ["abcd", "bcd", "acd", "cd", "ad"], "-d")
    def test_contracting_2(self):
        self.do_generator_test(["abcd%1,2-"], ["abc", "ab"], "-d")
    def test_contracting_right(self):
        self.do_generator_test(["ab%0,1>cd"], ["abcd", "abd"], "-d")
    def test_contracting_left(self):
        self.do_generator_test(["ab%0,3<cd"], ["abcd", "acd", "cd"], "-d")
    def test_contracting_multiple(self):
        self.do_generator_test(["%0,2-ab%[X]cd%0,2-"],
            ["abXcd", "abXc", "abX", "bXcd", "bXc", "bX", "Xcd", "Xc", "X"], "-d")


class Test04Typos(GeneratorTester):

    def test_capslock(self):
        self.do_generator_test(["One2Three"], ["One2Three", "oNE2tHREE"],
            "--typos-capslock --typos 2 -d", test_passwordlist=True)
    def test_capslock_nocaps(self):
        self.do_generator_test(["123"], ["123"],
            "--typos-capslock --typos 2 -d", test_passwordlist=True)

    def test_swap(self):
        self.do_generator_test(["abcdd"], ["abcdd", "bacdd", "acbdd", "abdcd", "badcd"],
            "--typos-swap --typos 2 -d", test_passwordlist=True)

    def test_repeat(self):
        self.do_generator_test(["abc"], ["abc", "aabc", "abbc", "abcc", "aabbc", "aabcc", "abbcc"],
            "--typos-repeat --typos 2 -d", test_passwordlist=True)

    def test_delete(self):
        self.do_generator_test(["abc"], ["abc", "bc", "ac", "ab", "c", "b", "a"],
            "--typos-delete --typos 2 -d", test_passwordlist=True)

    def test_case(self):
        self.do_generator_test(["abC1"], ["abC1", "AbC1", "aBC1", "abc1", "ABC1", "Abc1", "aBc1"],
            "--typos-case --typos 2 -d", test_passwordlist=True)

    def test_closecase(self):
        self.do_generator_test(["one2Three"],
            ["one2Three", "One2Three", "one2three", "one2THree", "one2ThreE", "One2three",
            "One2THree", "One2ThreE", "one2tHree", "one2threE", "one2THreE"],
            "--typos-closecase --typos 2 -d", test_passwordlist=True)

    def test_insert(self):
        self.do_generator_test(["abc"], ["abc", "aXbc", "abXc", "abcX", "aXbXc", "aXbcX", "abXcX" ],
            "--typos-insert X --typos 2 -d", test_passwordlist=True)
    def test_insert_wildcard(self):
        self.do_generator_test(["abc"], ["abc", "aXbc", "aYbc", "abXc", "abYc", "abcX", "abcY" ],
            "--typos-insert %[XY] -d", test_passwordlist=True)
    def test_insert_invalid(self):
        self.expect_syntax_failure(["abc"], "contracting wildcards are not permitted here",
            "--typos-insert %0,1-", test_passwordlist=True)

    def test_replace(self):
        self.do_generator_test(["abc"], ["abc", "Xbc", "aXc", "abX", "XXc", "XbX", "aXX" ],
            "--typos-replace X --typos 2 -d", test_passwordlist=True)
    def test_replace_wildcard(self):
        self.do_generator_test(["abc"], ["abc", "Xbc", "Ybc", "aXc", "aYc", "abX", "abY" ],
            "--typos-replace %[X-Y] -d", test_passwordlist=True)
    def test_replace_invalid(self):
        self.expect_syntax_failure(["abc"], "contracting wildcards are not permitted here",
            "--typos-replace %>", test_passwordlist=True)

    def test_map(self):
        self.do_generator_test(["axb"],
            ["axb", "Axb", "Bxb", "axA", "axB", "AxA", "AxB", "BxA", "BxB" ],
            "--typos-map __funccall --typos 2 -d",
            typos_map=cStringIO.StringIO(" ab \t AB \n x x \n a aB "))

    def test_z_all(self):
        self.do_generator_test(["ab"],
            ["ab","aab","b","Ab","aXb","Yb","abb","a","aB","abX","aY","aabb","aa","aaB","aabX",
            "aaY","bb","","B","bX","Y","Abb","A","AB","AbX","AY","aXbb","aX","aXB","aXbX","aXY",
            "Ybb","Y","YB","YbX","YY","ba","bba","a","Ba","bXa","Ya","baa","b","bA","baX","bY"],
            "--typos-swap --typos-repeat --typos-delete --typos-case --typos-insert X --typos-replace Y --typos 2 -d",
            test_passwordlist=True)

    def test_z_min_typos_1(self):
        self.do_generator_test(["ab"],
            ["aabb","aa","aaB","aabX","aaY","bb","","B","bX","Y","Abb","A","AB","AbX","AY","aXbb","aX",
            "aXB","aXbX","aXY","Ybb","Y","YB","YbX","YY","bba","a","Ba","bXa","Ya","baa","b","bA","baX","bY"],
            "--typos-swap --typos-repeat --typos-delete --typos-case --typos-insert X --typos-replace Y --typos 2 -d --min-typos 2",
            test_passwordlist=True)

    def test_z_min_typos_2(self):
        self.do_generator_test(["ab"], [],
            "--typos-swap --typos-repeat --typos-delete --typos-case --typos-insert X --typos-replace Y --typos 4 -d --min-typos 4",
            test_passwordlist=True)

class Test05CommandLine(GeneratorTester):

    def test_regex_only(self):
        self.do_generator_test(["one", "two"], ["one", "twoone", "onetwo"], "--regex-only o.e")

    def test_regex_never(self):
        self.do_generator_test(["one", "two"], ["two"], "--regex-never o.e")

    def test_delimiter_1(self):
        self.do_generator_test([" one ** two **** "], [" one ", " two ", "", " "], "--delimiter **")

    def test_delimiter_2(self):
        self.do_generator_test(["axb"], ["axb", "Axb", " xb", "axA", "ax ", "AxA", "Ax ", " xA", " x " ],
            "--delimiter ** --typos-map __funccall --typos 2 -d",
            typos_map=cStringIO.StringIO(" ab **A \n x **x"))

    def test_skip(self):
        btcrecover.parse_arguments(("--skip 2 --tokenlist __funccall --listpass").split(),
            tokenlist = cStringIO.StringIO("one \n two"))
        self.assertIn("2 password combinations (plus 2 skipped)", btcrecover.main())

    def test_worker(self):
        self.do_generator_test(["one two three four five six seven eight"], ["one", "four", "seven"],
            "--worker 1/3")
        self.do_generator_test(["one two three four five six seven eight"], ["two", "five", "eight"],
            "--worker 2/3")
        self.do_generator_test(["one two three four five six seven eight"], ["three", "six"],
            "--worker 3/3")

    def test_no_dupchecks_1(self):
        self.do_generator_test(["one", "one"], ["one", "one", "oneone", "oneone"], "-ddd")
        self.do_generator_test(["one", "one"], ["one", "one", "oneone"], "-dd")

    def test_no_dupchecks_2(self):
        self.do_generator_test(["one", "one"], ["one", "oneone"], "-d")
        # Duplicate code works differently the second time around; test it also
        self.assertEqual(list(btcrecover.password_generator()), ["one", "oneone"])

    def test_no_dupchecks_3(self):
        self.do_generator_test(["%[ab] %[a-b]"], ["a", "b", "a", "b"], "-d")
        self.do_generator_test(["%[ab] %[a-b]"], ["a", "b"])
        # Duplicate code works differently the second time around; test it also
        self.assertEqual(list(btcrecover.password_generator()), ["a", "b"])

SAVESLOT_SIZE = 4096
class Test06AutosaveRestore(unittest.TestCase):

    autosave_file = StringIONonClosing()

    def run_autosave_parse_arguments(self, autosave_file):
        btcrecover.parse_arguments(
            ("--autosave __funccall --tokenlist __funccall --privkey --no-progress --threads 1").split(),
            autosave  = autosave_file,
            tokenlist = cStringIO.StringIO("^one \n two \n three"),
            privkey   = "bWI6oikebfNQTLk75CfI5X3svX6AC7NFeGsgTNXZfA==")

    def run_restore_parse_arguments(self, restore_file):
        btcrecover.parse_arguments("--restore __funccall".split(),
            restore   = restore_file,
            tokenlist = cStringIO.StringIO("^one \n two \n three"),
            privkey   = "bWI6oikebfNQTLk75CfI5X3svX6AC7NFeGsgTNXZfA==")

    # These test_ functions are in alphabetical order (the same order they're executed in)

    # Create the initial autosave data
    def test_autosave(self):
        autosave_file = self.__class__.autosave_file
        self.run_autosave_parse_arguments(autosave_file)
        self.assertIn("Password search exhausted", btcrecover.main())
        #
        # Load slot 0, and verify it was created before any passwords were tested
        autosave_file.seek(0)
        savestate = cPickle.load(autosave_file)
        self.assertEqual(savestate.get("skip"), 0)
        self.assertLessEqual(autosave_file.tell(), SAVESLOT_SIZE)
        #
        # Load slot 1, and verify it was created after all passwords were tested
        autosave_file.seek(SAVESLOT_SIZE)
        savestate = cPickle.load(autosave_file)
        self.assertEqual(savestate.get("skip"), 9)
        self.assertLessEqual(autosave_file.tell(), 2*SAVESLOT_SIZE)

    # Using --autosave, restore (a copy of) the autosave data created by test_autosave(),
    # and make sure all of the passwords have already been tested
    def test_autosave_restore(self):
        self.run_autosave_parse_arguments(StringIONonClosing(self.__class__.autosave_file.getvalue()))
        self.assertIn("Skipped all 9 passwords, exiting", btcrecover.main())

    # Using --restore, restore (a copy of) the autosave data created by test_autosave(),
    # and make sure all of the passwords have already been tested
    def test_restore(self):
        self.run_restore_parse_arguments(StringIONonClosing(self.__class__.autosave_file.getvalue()))
        self.assertIn("Skipped all 9 passwords, exiting", btcrecover.main())

    # Using --autosave, restore (a copy of) the autosave data created by test_autosave(),
    # but change the arguments to generate an error
    def test_restore_changed_args(self):
        with self.assertRaises(SystemExit) as cm:
            btcrecover.parse_arguments(
                ("--autosave __funccall --tokenlist __funccall --privkey --no-progress --threads 1 --max-tokens 1").split(),
                autosave  = StringIO.StringIO(self.__class__.autosave_file.getvalue()),
                tokenlist = cStringIO.StringIO("^one \n two \n three"),
                privkey   = "bWI6oikebfNQTLk75CfI5X3svX6AC7NFeGsgTNXZfA==")
        self.assertIn("can't restore previous session: the command line options have changed", cm.exception.code)

    # Using --autosave, restore (a copy of) the autosave data created by test_autosave(),
    # but change the tokenlist file to generate an error
    def test_restore_changed_tokenlist(self):
        with self.assertRaises(SystemExit) as cm:
            btcrecover.parse_arguments(
                ("--autosave __funccall --tokenlist __funccall --privkey --no-progress --threads 1").split(),
                autosave  = StringIO.StringIO(self.__class__.autosave_file.getvalue()),
                tokenlist = cStringIO.StringIO("three \n two \n ^one"),
                privkey   = "bWI6oikebfNQTLk75CfI5X3svX6AC7NFeGsgTNXZfA==")
        self.assertIn("can't restore previous session: the tokenlist file has changed", cm.exception.code)

    # Using --restore, restore (a copy of) the autosave data created by test_autosave(),
    # but change the privkey data to generate an error
    def test_restore_changed_privkey(self):
        with self.assertRaises(SystemExit) as cm:
            btcrecover.parse_arguments(
                ("--restore __funccall").split(),
                restore   = StringIO.StringIO(self.__class__.autosave_file.getvalue()),
                tokenlist = cStringIO.StringIO("^one \n two \n three"),
                privkey   = "bWI6ACkebfNQTLk75CfI5X3svX6AC7NFeGsgUxKNFg==")
        self.assertIn("can't restore previous session: the encrypted key entered is not the same", cm.exception.code)

    # Using --restore, restore the autosave data created by test_autosave(),
    # but remove the last byte from slot 1 to make it invalid
    def test_restore_truncated(self):
        autosave_file = self.__class__.autosave_file
        autosave_file.seek(-1, os.SEEK_END)
        autosave_file.truncate()
        self.run_restore_parse_arguments(autosave_file)
        #
        # Slot 1 had the final save, but since it is invalid, the loader should fall
        # back to slot 0 with the initial save, so the passwords should be tried again.
        self.assertIn("Password search exhausted", btcrecover.main())
        #
        # Because slot 1 was invalid, it is the first slot overwritten. Load slot 0
        # (the second slot overwritten), and verify it was written to after all
        # passwords were tested
        autosave_file.seek(0)
        savestate = cPickle.load(autosave_file)
        self.assertEqual(savestate.get("skip"), 9)
        #
        # Load slot 1, and verify it was written to before any passwords were tested
        autosave_file.seek(SAVESLOT_SIZE)
        savestate = cPickle.load(autosave_file)
        self.assertEqual(savestate.get("skip"), 0)


class Test07WalletDecryption(unittest.TestCase):

    # Checks a test wallet against the known password, and ensures
    # that the library doesn't make any changes to the wallet file
    def wallet_tester(self, wallet_basename, force_purepython = False):
        assert os.path.basename(wallet_basename) == wallet_basename
        wallet_filename = os.path.join(wallet_dir, wallet_basename)

        temp_dir = tempfile.mkdtemp("-test-btcr")
        temp_wallet_filename = os.path.join(temp_dir, wallet_basename)
        shutil.copyfile(wallet_filename, temp_wallet_filename)

        btcrecover.load_wallet(temp_wallet_filename)
        if force_purepython: btcrecover.load_aes256_library(True)

        self.assertFalse(btcrecover.return_verified_password_or_false("btcr-wrong-password"))
        self.assertEqual(btcrecover.return_verified_password_or_false("btcr-test-password"), "btcr-test-password")

        btcrecover.unload_wallet()
        self.assertTrue(filecmp.cmp(wallet_filename, temp_wallet_filename, False))  # False == always compare file contents
        shutil.rmtree(temp_dir)

    def test_armory(self):
        self.wallet_tester("armory-wallet.wallet")

    @unittest.skipUnless(btcrecover.load_aes256_library().__name__ == "Crypto", "requires PyCrypto")
    def test_bitcoincore(self):
        self.wallet_tester("bitcoincore-wallet.dat")

    @unittest.skipUnless(btcrecover.load_aes256_library().__name__ == "Crypto", "requires PyCrypto")
    def test_electrum(self):
        self.wallet_tester("electrum-wallet")

    @unittest.skipUnless(btcrecover.load_aes256_library().__name__ == "Crypto", "requires PyCrypto")
    def test_multibit(self):
        self.wallet_tester("multibit-wallet.key")

    def test_bitcoincore_pp(self):
        self.wallet_tester("bitcoincore-wallet.dat", True)

    def test_electrum_pp(self):
        self.wallet_tester("electrum-wallet", True)

    def test_multibit_pp(self):
        self.wallet_tester("multibit-wallet.key", True)

    def test_invalid_wallet(self):
        with self.assertRaises(SystemExit) as cm:
            btcrecover.load_wallet(__file__)
        self.assertIn("unrecognized wallet format", cm.exception.code)


class Test08KeyDecryption(unittest.TestCase):

    def key_tester(self, key_crc_base64, force_purepython = False):
        btcrecover.load_from_base64_key(key_crc_base64)
        if force_purepython: btcrecover.load_aes256_library(True)

        self.assertFalse(btcrecover.return_verified_password_or_false("btcr-wrong-password"))
        self.assertEqual(btcrecover.return_verified_password_or_false("btcr-test-password"), "btcr-test-password")

    def test_armory(self):
        self.key_tester("YXI6r7mks1qvph4G+rRT7WlIptdr9qDqyFTfXNJ3ciuWJ12BgWX5Il+y28hLNr/u4Wl49hUi4JBeq6Jz9dVBX3vAJ6476FEAACAABAAAAGGwnwXRpPbBzC5lCOBVVWDu7mUJetBOBvzVAv0IbrboDXqA8A==")

    @unittest.skipUnless(btcrecover.load_aes256_library().__name__ == "Crypto", "requires PyCrypto")
    def test_bitcoincore(self):
        self.key_tester("YmM6Liw7m1jpszyXmbRHLoPBNuYkYSDEXjkNqmpXR25/vk9X2D9511+bTB22gP5ahGy4RZOv9WORecdECQEA9h79LQ==")

    @unittest.skipUnless(btcrecover.load_aes256_library().__name__ == "Crypto", "requires PyCrypto")
    def test_multibit(self):
        self.key_tester("bWI6oikebfNQTLk75CfI5X3svX6AC7NFeGsgTNXZfA==")

    def test_bitcoincore_pp(self):
        self.key_tester("YmM6Liw7m1jpszyXmbRHLoPBNuYkYSDEXjkNqmpXR25/vk9X2D9511+bTB22gP5ahGy4RZOv9WORecdECQEA9h79LQ==", True)

    def test_multibit_pp(self):
        self.key_tester("bWI6oikebfNQTLk75CfI5X3svX6AC7NFeGsgTNXZfA==", True)

    def test_invalid_crc(self):
        with self.assertRaises(SystemExit) as cm:
            self.key_tester("aWI6oikebfNQTLk75CfI5X3svX6AC7NFeGsgTNXZfA==")
        self.assertIn("encrypted key data is corrupted (failed CRC check)", cm.exception.code)


class Test09EndToEnd(unittest.TestCase):

    autosave_file = StringIONonClosing()

    # These test_ functions are in alphabetical order (the same order they're executed in)

    def test_end_to_end(self):
        autosave_file = self.__class__.autosave_file
        btcrecover.parse_arguments(
            "--tokenlist __funccall --privkey --autosave __funccall --typos 3 --typos-case --typos-repeat --typos-swap --no-progress".split(),
            tokenlist = cStringIO.StringIO("\n".join(
                ["+ ^%0,1[b-c]tcr--", "+ ^,$%0,1<Test-", "^3$pas", "+ wrod$"]
            )),
            privkey   = "bWI6oikebfNQTLk75CfI5X3svX6AC7NFeGsgTNXZfA==",
            autosave  = autosave_file)

        self.assertIn("Password found: 'btcr-test-password'", btcrecover.main())

        # Verify the exact password number where it was found
        autosave_file.seek(SAVESLOT_SIZE)
        savestate = cPickle.load(autosave_file)
        self.assertEqual(savestate.get("skip"), 103764)

    def test_restore(self):
        self.test_end_to_end()

        # Verify the password number where the search started
        autosave_file = self.__class__.autosave_file
        autosave_file.seek(0)
        savestate = cPickle.load(autosave_file)
        self.assertEqual(savestate.get("skip"), 103764)


if __name__ == '__main__':
    unittest.main(buffer = True)
