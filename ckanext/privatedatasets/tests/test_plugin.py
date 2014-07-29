import unittest
import ckanext.privatedatasets.plugin as plugin

from mock import MagicMock
from nose_parameterized import parameterized


class PluginTest(unittest.TestCase):

    def setUp(self):
        # Create mocks
        self._tk = plugin.tk
        plugin.tk = MagicMock()

        self._db = plugin.db
        plugin.db = MagicMock()

        self._search = plugin.search
        plugin.search = MagicMock()

        # Create the plugin
        self.privateDatasets = plugin.PrivateDatasets()

    def tearDown(self):
        plugin.tk = self._tk
        plugin.db = self._db
        plugin.search = self._search

    @parameterized.expand([
        (plugin.p.IDatasetForm,),
        (plugin.p.IAuthFunctions,),
        (plugin.p.IConfigurer,),
        (plugin.p.IRoutes,),
        (plugin.p.IActions,),
        (plugin.p.IPackageController,),
        (plugin.p.ITemplateHelpers,)
    ])
    def test_implementation(self, interface):
        self.assertTrue(interface.implemented_by(plugin.PrivateDatasets))

    @parameterized.expand([
        ('package_show',     plugin.auth.package_show),
        ('package_update',   plugin.auth.package_update),
        ('package_show',     plugin.auth.package_show),
        ('package_adquired', plugin.auth.package_adquired)
    ])
    def test_auth_function(self, function_name, expected_function):
        auth_functions = self.privateDatasets.get_auth_functions()
        self.assertEquals(auth_functions[function_name], expected_function)

    def test_update_config(self):
        # Call the method
        config = {'test': 1234, 'another': 'value'}
        self.privateDatasets.update_config(config)

        # Test that functions are called as expected
        plugin.tk.add_template_directory.assert_called_once_with(config, 'templates')
        plugin.tk.add_resource('fanstatic', 'privatedatasets')

    def test_map(self):
        # Call the method
        m = MagicMock()
        self.privateDatasets.before_map(m)

        # Test that the connect method has been called
        m.connect.assert_any_call('user_adquired_datasets', '/dashboard/adquired', ckan_icon='shopping-cart',
                                  controller='ckanext.privatedatasets.controllers.ui_controller:AdquiredDatasetsControllerUI',
                                  action='user_adquired_datasets', conditions=dict(method=['GET']))

    @parameterized.expand([
        ('package_adquired', plugin.actions.package_adquired)
    ])
    def test_actions_function(self, function_name, expected_function):
        actions = self.privateDatasets.get_actions()
        self.assertEquals(actions[function_name], expected_function)

    def test_fallback(self):
        self.assertEquals(True, self.privateDatasets.is_fallback())

    def test_package_types(self):
        self.assertEquals([], self.privateDatasets.package_types())

    @parameterized.expand([
        ('privatedatasets_adquired', plugin.helpers.is_adquired),
        ('get_allowed_users_str',    plugin.helpers.get_allowed_users_str),
        ('is_owner',                 plugin.helpers.is_owner),
        ('can_read',                 plugin.helpers.can_read)
    ])
    def test_helpers_functions(self, function_name, expected_function):
        helpers_functions = self.privateDatasets.get_helpers()
        self.assertEquals(helpers_functions[function_name], expected_function)

    ######################################################################
    ############################## SCHEMAS ###############################
    ######################################################################

    def _check_fields(self, schema, fields):
        for field in fields:
            for checker_validator in fields[field]:
                self.assertTrue(checker_validator in schema[field])
            self.assertEquals(len(fields[field]), len(schema[field]))

    @parameterized.expand([
        ('create_package_schema'),
        ('update_package_schema'),
    ])
    def test_schema_create_update(self, function_name):
  
        function = getattr(self.privateDatasets, function_name)
        returned_schema = function()

        fields = {
            'private': [plugin.tk.get_validator('ignore_missing'), plugin.tk.get_validator('boolean_validator')],
            'adquire_url': [plugin.tk.get_validator('ignore_missing'), plugin.tk.get_converter('convert_to_extras'),
                            plugin.conv_val.url_checker, plugin.conv_val.private_datasets_metadata_checker],
            'searchable': [plugin.tk.get_validator('ignore_missing'), plugin.tk.get_validator('boolean_validator'),
                           plugin.tk.get_converter('convert_to_extras'), plugin.conv_val.private_datasets_metadata_checker],
            'allowed_users_str': [plugin.tk.get_validator('ignore_missing'), plugin.conv_val.private_datasets_metadata_checker],
            'allowed_users': [plugin.conv_val.allowed_users_convert, plugin.tk.get_validator('ignore_missing'),
                              plugin.conv_val.private_datasets_metadata_checker]
        }

        self._check_fields(returned_schema, fields)

    def test_schema_show(self):

        returned_schema = self.privateDatasets.show_package_schema()
   
        fields = ['searchable', 'adquire_url']

        fields = {
            'adquire_url': [plugin.tk.get_validator('ignore_missing'), plugin.tk.get_converter('convert_from_extras')],
            'searchable': [plugin.tk.get_validator('ignore_missing'), plugin.tk.get_converter('convert_from_extras')],
            'allowed_users': [plugin.tk.get_validator('ignore_missing'), plugin.conv_val.get_allowed_users]
        }

        self._check_fields(returned_schema, fields)

    ######################################################################
    ############################## PACKAGE ###############################
    ######################################################################

    @parameterized.expand([
        ('True',  []),
        ('False', []),
        ('True',  ['abc']),
        ('False', ['abc']),
        ('True',  ['abc', 'def', 'ghi']),
        ('False', ['abc', 'def', 'ghi']),
    ])
    def test_packagecontroller_after_delete(self, private, allowed_users):
        pkg_id = '29472'
        pkg_dict = {'test': 'a', 'id': pkg_id, 'private': private, 'allowed_users': allowed_users}
        expected_pkg_dict = pkg_dict.copy()

        # Configure the database mock
        db_current_users = []
        for user in allowed_users:
            db_user = MagicMock()
            db_user.package_id = pkg_id
            db_user.user_name = user
            db_current_users.append(db_user)

        # Allowed users
        plugin.db.AllowedUser.get = MagicMock(return_value=db_current_users)

        context = {'user': 'test', 'auth_user_obj': {'id': 1}, 'session': MagicMock(), 'model': MagicMock()}
        result = self.privateDatasets.after_delete(context, pkg_dict)   # Call the function
        self.assertEquals(expected_pkg_dict, result)                    # Check the result

        # Assert that the get method has been called
        plugin.db.AllowedUser.get.assert_called_once_with(package_id=pkg_id)

        # Check that all the users has been deleted
        for user in allowed_users:
            found = False
            for call in context['session'].delete.call_args_list:
                call_user = call[0][0]

                if call_user.package_id == pkg_id and call_user.user_name == user:
                    found = True
                    break

            self.assertTrue(found)

    @parameterized.expand([
        (True,  1, 1,    False, True),
        (True,  1, 2,    False, True),
        (True,  1, 1,    True,  True),
        (True,  1, 2,    True,  True),
        (True,  1, None, None,  True),
        (True,  1, 1,    None,  True),
        (True,  1, None, True,  True),
        (True,  1, None, False, True),
        (False, 1, 1,    False, True),
        (False, 1, 2,    False, False),
        (False, 1, 1,    True,  True),
        (False, 1, 2,    True,  True),
        (False, 1, None, None,  False),
        (False, 1, 1,    None,  True),
        (False, 1, None, True,  True),
        (False, 1, None, False, False),
    ])
    def test_packagecontroller_after_show(self, update_via_api, creator_id, user_id, sysadmin, fields_expected):
        
        context = {'updating_via_cb': update_via_api}

        if creator_id is not None or sysadmin is not None:
            user = MagicMock()
            user.id = user_id
            user.sysadmin = sysadmin
            context['auth_user_obj'] = user

        pkg_dict = {'creator_user_id': creator_id, 'allowed_users': ['a', 'b', 'c'], 'searchable': True, 'adquire_url': 'http://google.es'}

        # Call the function
        result = self.privateDatasets.after_show(context, pkg_dict)    # Call the function

        # Check the final result
        fields = ['allowed_users', 'searchable', 'adquire_url']
        for field in fields:
            if fields_expected:
                self.assertTrue(field in result)
            else:
                self.assertFalse(field in result)

    @parameterized.expand([
        ('public',  None,    'public'),
        ('public',  'False', 'private'),
        ('public',  'True',  'public'),
        ('private', None,    'private'),
        ('private', 'False', 'private'),
        ('public',  'True',  'public')
    ])
    def test_before_index(self, initialCapacity, searchable, finalCapacity):
        pkg_dict = {'capacity': initialCapacity, 'name': 'a', 'description': 'This is a test'}
        if searchable is not None:
            pkg_dict['extras_searchable'] = searchable

        expected_result = pkg_dict.copy()
        expected_result['capacity'] = finalCapacity

        self.assertEquals(expected_result, self.privateDatasets.before_index(pkg_dict))

    def _aux_test_after_create_update(self, function, new_users, current_users, users_to_add, users_to_delete):
        package_id = 'package_id'

        # Configure mocks
        default_dict = {'a': '0', 'b': 1, 'm': True}
        package_show = MagicMock(return_value=default_dict)
        plugin.tk.get_action = MagicMock(return_value=package_show)

        # Each time 'AllowedUser' is called, we must get a new instance
        # and this is the way to get this behaviour
        def constructor():
            return MagicMock()

        plugin.db.AllowedUser = MagicMock(side_effect=constructor)

        # Configure the database mock
        db_current_users = []
        for user in current_users:
            db_user = MagicMock()
            db_user.package_id = package_id
            db_user.user_name = user
            db_current_users.append(db_user)

        plugin.db.AllowedUser.get = MagicMock(return_value=db_current_users)

        # Call the method
        context = {'user': 'test', 'auth_user_obj': {'id': 1}, 'session': MagicMock(), 'model': MagicMock()}
        pkg_dict = {'id': 'package_id', 'allowed_users': new_users}
        function(context, pkg_dict)

        def _test_calls(user_list, function):
            self.assertEquals(len(user_list), function.call_count)
            for user in user_list:
                found = False
                for call in function.call_args_list:
                    call_user = call[0][0]

                    if call_user.package_id == package_id and call_user.user_name == user:
                        found = True
                        break

                self.assertTrue(found)

        # Check that the method has deleted the appropriate users
        _test_calls(users_to_delete, context['session'].delete)

        # Check that the method has added the appropiate users
        _test_calls(users_to_add, context['session'].add)

        if len(users_to_add) == 0 and len(users_to_delete) == 0:
            # Check that the cache has not been updated
            self.assertEquals(0, self.privateDatasets.indexer.update_dict.call_count)
        else:
            # Check that the cache has been updated
            self.privateDatasets.indexer.update_dict.assert_called_once_with(default_dict)

    @parameterized.expand([
        # One element
        (['a'],           [],              ['a'],           []),
        (['a'],           ['a'],           [],              []),
        ([],              ['a'],           [],              ['a']),
        # Two elements
        (['a', 'b'],      [],              ['a', 'b'],      []),
        (['a', 'b'],      ['b'],           ['a'],           []),
        (['a'],           ['a', 'b'],      [],              ['b']),
        ([],              ['a', 'b'],      [],              ['a', 'b']),
        (['a', 'b'],      ['a', 'b'],      [],              []),
        # Three or more elements
        (['c'],           ['a', 'b'],      ['c'],           ['a', 'b']),
        (['a', 'b', 'c'], ['a', 'b'],      ['c'],           []),
        (['a', 'b', 'c'], ['a'],           ['b', 'c'],      []),
        (['a', 'b', 'c'], ['a', 'b', 'c'], [],              []),
        (['a', 'b', 'c'], [],              ['a', 'b', 'c'], []),
        (['a', 'b'],      ['a', 'b', 'c'], [],              ['c'])
    ])
    def test_after_create(self, new_users, current_users, users_to_add, users_to_delete):
        self._aux_test_after_create_update(self.privateDatasets.after_create, new_users, current_users, users_to_add, users_to_delete)

    @parameterized.expand([
        # One element
        (['a'],           [],              ['a'],           []),
        (['a'],           ['a'],           [],              []),
        ([],              ['a'],           [],              ['a']),
        # Two elements
        (['a', 'b'],      [],              ['a', 'b'],      []),
        (['a', 'b'],      ['b'],           ['a'],           []),
        (['a'],           ['a', 'b'],      [],              ['b']),
        ([],              ['a', 'b'],      [],              ['a', 'b']),
        (['a', 'b'],      ['a', 'b'],      [],              []),
        # Three or more elements
        (['c'],           ['a', 'b'],      ['c'],           ['a', 'b']),
        (['a', 'b', 'c'], ['a', 'b'],      ['c'],           []),
        (['a', 'b', 'c'], ['a'],           ['b', 'c'],      []),
        (['a', 'b', 'c'], ['a', 'b', 'c'], [],              []),
        (['a', 'b', 'c'], [],              ['a', 'b', 'c'], []),
        (['a', 'b'],      ['a', 'b', 'c'], [],              ['c'])
    ])
    def test_after_update(self, new_users, current_users, users_to_add, users_to_delete):
        self._aux_test_after_create_update(self.privateDatasets.after_update, new_users, current_users, users_to_add, users_to_delete)
