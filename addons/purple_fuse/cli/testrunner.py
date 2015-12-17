from __future__ import print_function

import argparse
import contextlib
import logging
import textwrap
import types
import unittest

from openerp.cli import Command
from openerp.tools import config
import openerp

import purplespade

try:
    import coverage
    has_coverage = True
except:
    has_coverage = False


class Unittest(Command):
    """Unittest runner"""
    epilog = """
        Python unittest with Odoo context

        Examples:
            %(prog)s                           - run ALL tests
            %(prog)s addon                     - run all test of addon
            %(prog)s asson.tests.TestClass     - run tests from addon.TestClass
            %(prog)s addon.tests.TestClass.test_method  - run specified test method
    """

    def run(self, args):
        options = self.parse_args(args)
        if options.scratch:
            purplespade.drop_database(options.database)

        self.set_logging(options.log in ['init', 'all'])
        if options.database:
            config['db_name'] = options.database
        with self.enclose_openerp_api(options):
            config['skipif'] = options.skipif
            with self.coverage_report(options.cover):
                self.execute_tests(
                    options.tests,
                    options.verbosity,
                    log=options.log in ['test', 'all']
                )

    @contextlib.contextmanager
    def enclose_openerp_api(self, options):
        init = options.init and dict.fromkeys(options.init.split(','), 1) or {}
        update = options.update and dict.fromkeys(options.update.split(','), 1) or {}
        need_env = not options.fast and not init and not update
        if not need_env:
            yield
        else:
            with purplespade.openerp_env(
                db_name=options.database,
                without_demo=options.without_demo,
                init=init,
                update=update
            ):
                yield

    def execute_tests(self, tests, verbosity, log):
        if tests:
            suite = self.build_test_suite(tests)
        else:
            suite = self.build_all_tests_suite()
        runner = unittest.TextTestRunner(
            verbosity=verbosity
        )
        self.set_logging(log)
        runner.run(suite)

    def build_test_suite(self, tests):
        suite = unittest.TestSuite()
        loader = unittest.TestLoader()
        for test in tests:
            if "." in test:
                suite.addTests(loader.loadTestsFromNames(
                    [self.ensure_addon_prefix(test)]
                ))
            else:
                suite.addTests(self.build_addon_test_suite(test))
        return suite

    def build_all_tests_suite(self):
        suite = unittest.TestSuite()
        exclude = ['base', 'base_import']
        for key, obj in openerp.addons.__dict__.iteritems():
            if type(obj) is types.ModuleType and key not in exclude:
                suite.addTests(self.build_addon_test_suite(key))
        return suite

    def build_addon_test_suite(self, name):
        suite = unittest.TestSuite()
        loader = unittest.TestLoader()
        for m in openerp.modules.module.get_test_modules(name):
            suite.addTests(loader.loadTestsFromModule(m))
        return suite

    def set_logging(self, log=True):
        if log:
            logging.disable(0)
        else:
            logging.disable(100)

    def ensure_addon_prefix(self, addon_name):
        if not addon_name.startswith('openerp.addons.'):
            return 'openerp.addons.' + addon_name
        return addon_name

    def parse_args(self, args):
        parser = self.get_parser()
        options = parser.parse_args(args)
        return options

    def get_parser(self):
        doc_paras = self.__doc__.split('\n\n')
        parser = argparse.ArgumentParser(
            description=doc_paras[0],
            epilog=textwrap.dedent(self.epilog),
            prog="odoo-server test",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            '-d', '--database', dest='database', default=config['db_name'],
            help="Build test database (default: %s)" % config['db_name']
        )
        parser.add_argument(
            '--scratch', dest='scratch', action='store_true',
            help="Recreate database before test"
        )
        parser.add_argument(
            '-i', '--init', dest='init', default='',
            help="Init modules, coma separated list"
        )
        parser.add_argument(
            '-u', '--update', dest='update', default='',
            help="Update modules, coma separated list"
        )
        parser.add_argument(
            '--without-demo', dest='without_demo',
            default='',
            help="""disable loading demo data for modules to be installed
                (comma-separated, use "all" for all modules)
                By default loads demo data """
        )
        parser.add_argument(
            '--coverage', dest='cover', default=None,
            help="""Build test coverage report. Requires coverage package."""
        )
        parser.add_argument(
            '--skipif', dest='skipif',
            default=None,
            help="""Set openerp config 'skipif' value. Can be used for
                conditional skipping."""
        )
        parser.add_argument(
            '--fast', dest='fast', action='store_true', default=False,
            help="Try to not initialise OpenERP \
                - make test runner much faster however does no effecft with \
                  -i or -u"
        )
        parser.add_argument(
            '-v', '--verbosity', type=int, default=2,
            help="Test verbosity (default: 2)"
        )
        parser.add_argument(
            '--log',
            choices=["none", "init", "test", "all"],
            default="init",
            help="Control which part of code can write logs"
        )
        parser.add_argument(
            'tests', nargs="*",
            help="can be a list of any number of test modules, classes and test \
            methods."
        )
        return parser

    @contextlib.contextmanager
    def coverage_report(self, cover):
        if cover:
            if not has_coverage:
                raise Exception("Coverage package have to be installed")
            cov = coverage.coverage(branch=True)
            cov.start()
        try:
            yield
        finally:
            if cover:
                cov.stop()
                cov.save()
                cov.report(include=cover)
