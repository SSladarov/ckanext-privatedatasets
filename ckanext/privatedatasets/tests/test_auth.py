import unittest
import ckanext.privatedatasets.auth as auth

from mock import MagicMock
from nose_parameterized import parameterized


class AuthTest(unittest.TestCase):

    def setUp(self):
        # Create mocks
        self._logic_auth = auth.logic_auth
        auth.logic_auth = MagicMock()

        self._request = auth.request
        auth.request = MagicMock()

        self._helpers = auth.helpers
        auth.helpers = MagicMock()

        self._new_authz = auth.new_authz
        auth.new_authz = MagicMock()

        self._tk = auth.tk
        auth.tk = MagicMock()

        self._db = auth.db
        auth.db = MagicMock()

    def tearDown(self):
        auth.logic_auth = self._logic_auth
        auth.request = self._request
        auth.helpers = self._helpers
        auth.new_authz = self._new_authz
        auth.tk = self._tk
        auth.db = self._db

        if hasattr(self, '_package_show'):
            auth.package_show = self._package_show

    def test_decordators(self):
        self.assertEquals(True, getattr(auth.package_show, 'auth_allow_anonymous_access', False))
        self.assertEquals(True, getattr(auth.resource_show, 'auth_allow_anonymous_access', False))
        self.assertEquals(True, getattr(auth.package_adquired, 'auth_allow_anonymous_access', False))

    @parameterized.expand([
        # Anonymous user (public)
        (None, None, None,   False, 'active', None,     None,  None,  None,        None,              True),
        # Anonymous user (private)
        (None, None, None,   True,  'active', None,     None,  None,  None,        '/',               False),
        (None, None, '',     True,  'active', None,     None,  '',    None,        '/',               False),
        # Anonymous user (private). Buy URL not shown
        (None, None, None,   True,  'active', None,     None,  None,  'google.es', '/',               False),
        # Anonymous user (private). Buy URL show
        (None, None, None,   True,  'active', None,     None,  None,  'google.es', '/dataset/testds', False),
        # The creator can always see the dataset
        (1,    1,    None,   False, 'active', None,     None,  None,  None,        None,              True),
        (1,    1,    None,   True,  'active', 'conwet', None,  None,  None,        None,              True),
        (1,    1,    None,   True,  'active', None,     None,  None,  None,        None,              True),
        (1,    1,    None,   False, 'draft',  None,     None,  None,  None,        None,              True),
        # Other user (no organizations)
        (1,    2,    'test', False, 'active', None,     None,  None,  None,        None,              True),
        (1,    2,    'test', True,  'active', None,     None,  None,  'google.es', '/',               False),  # Buy MSG not shown
        (1,    2,    'test', True,  'active', None,     None,  None,  None,        '/dataset/testds', False),  # Buy MSG not shown
        (1,    2,    'test', True,  'active', None,     None,  None,  'google.es', '/dataset/testds', False),  # Buy MSG shown
        (1,    2,    'test', False, 'draft',  None,     None,  None,  None,        None, False),
        # Other user but authorized in the list of authorized users
        (1,    2,    'test', True,  'active', None,     None,  True,  None,        None,              True),
        # Other user and not authorized in the list of authorized users
        (1,    2,    'test', True,  'active', None,     None,  False, 'google.es', '/',               False),
        (1,    2,    'test', True,  'active', None,     None,  False, 'google.es', '/dataset/testds', False),
        # Other user with organizations
        (1,    2,    'test', False, 'active', 'conwet', False, None,  None,        None,              True),
        (1,    2,    'test', True,  'active', 'conwet', False, None,  None,        None,              False),
        (1,    2,    'test', True,  'active', 'conwet', True,  None,  None,        None,              True),
        (1,    2,    'test', True,  'draft',  'conwet', True,  None,  None,        None,              False),
        # Other user with organizations (user is not in the organization)
        (1,    2,    'test', True,  'active', 'conwet', False, True,  None,        None,              True),
        (1,    2,    'test', True,  'active', 'conwet', False, False, None,        None,              False),
        (1,    2,    'test', True,  'active', 'conwet', False, False, 'google.es', '/dataset/testds', False),
        (1,    2,    'test', True,  'active', 'conwet', False, False, 'google.es', '/',               False)
    ])
    def test_auth_package_show(self, creator_user_id, user_obj_id, user, private, state, owner_org,
                               owner_member, db_auth, adquire_url, request_path, authorized):

        # Configure the mocks
        returned_package = MagicMock()
        returned_package.creator_user_id = creator_user_id
        returned_package.private = private
        returned_package.state = state
        returned_package.owner_org = owner_org
        returned_package.extras = {}

        # Configure the database
        db_response = []
        if db_auth is True:
            out = auth.db.AllowedUser()
            out.package_id = 'package_id'
            out.user_name = user
            db_response.append(out)

        auth.db.AllowedUser.get = MagicMock(return_value=db_response)

        if adquire_url:
            returned_package.extras['adquire_url'] = adquire_url

        auth.logic_auth.get_package_object = MagicMock(return_value=returned_package)
        auth.new_authz.has_user_permission_for_group_or_org = MagicMock(return_value=owner_member)
        auth.request.path = MagicMock(return_value=request_path)

        # Prepare the context
        context = {'model': MagicMock()}
        if user is not None:
            context['user'] = user
        if user_obj_id is not None:
            context['auth_user_obj'] = MagicMock()
            context['auth_user_obj'].id = user_obj_id

        # Function to be tested
        result = auth.package_show(context, {})

        # Check the result
        self.assertEquals(authorized, result['success'])

        # Premissions for organization are checked when the dataset is private, it belongs to an organization
        # and when the dataset has not been created by the user who is asking for it
        if private and owner_org and state == 'active' and creator_user_id != user_obj_id:
            auth.new_authz.has_user_permission_for_group_or_org.assert_called_once_with(owner_org, user, 'read')

        # The databse is only initialized when:
        # * the dataset is private AND
        # * the dataset is active AND
        # * the dataset has no organization OR the user does not belong to that organization AND
        # * the dataset has not been created by the user who is asking for it
        if private and state == 'active' and ((owner_org and not owner_org) or not owner_org) and creator_user_id != user_obj_id:
            # Check that the database has been initialized properly
            auth.db.init_db.assert_called_once_with(context['model'])

        # Conditions to buy a dataset; It should be private, active and should not belong to any organization
        if not authorized and state == 'active' and not owner_org and request_path.startswith('/dataset/'):
            auth.helpers.flash_error.assert_called_once()

    @parameterized.expand([
        (None, None, None,   None,     None,  False),   # Anonymous user
        (1,    1,    None,   None,     None,  True),    # A user can edit its dataset
        (1,    2,    None,   None,     None,  False),   # A user cannot edit a dataset belonging to another user
        (1,    2,    'test', 'conwet', False, False),   # User without rights to update a dataset
        (1,    2,    'test', 'conwet', True,  True),    # User with rights to update a dataset
    ])
    def test_auth_package_update(self, creator_user_id, user_obj_id, user, owner_org, owner_member, authorized):

        # Configure the mocks
        returned_package = MagicMock()
        returned_package.creator_user_id = creator_user_id
        returned_package.owner_org = owner_org

        auth.logic_auth.get_package_object = MagicMock(return_value=returned_package)
        auth.new_authz.has_user_permission_for_group_or_org = MagicMock(return_value=owner_member)

        # Prepare the context
        context = {}
        if user is not None:
            context['user'] = user
        if user_obj_id is not None:
            context['auth_user_obj'] = MagicMock()
            context['auth_user_obj'].id = user_obj_id

        # Function to be tested
        result = auth.package_update(context, {})

        # Check the result
        self.assertEquals(authorized, result['success'])

        # Check that the mock has been called properly
        if creator_user_id != user_obj_id and owner_org:
            auth.new_authz.has_user_permission_for_group_or_org.assert_called_once_with(owner_org, user, 'update_dataset')

    @parameterized.expand([
        (True,  True),
        (True,  False),
        (False, False),
        (False, False)
    ])
    def test_auth_resource_show(self, exist_pkg=True, authorized_pkg=True):
        #Recover the exception
        auth.tk.ObjectNotFound = self._tk.ObjectNotFound

        # Mock the calls
        package = MagicMock()
        package.id = '1'

        final_query = MagicMock()
        final_query.first = MagicMock(return_value=package if exist_pkg else None)

        second_join = MagicMock()
        second_join.filter = MagicMock(return_value=final_query)

        first_join = MagicMock()
        first_join.join = MagicMock(return_value=second_join)

        query = MagicMock()
        query.join = MagicMock(return_value=first_join)

        model = MagicMock()
        session = MagicMock()
        session.query = MagicMock(return_value=query)
        model.Session = session

        # Create the context
        context = {}
        context['model'] = model

        # Mock the package_show function
        self._package_show = auth.package_show
        success = True if authorized_pkg else False
        auth.package_show = MagicMock(return_value={'success': success})

        if not exist_pkg:
            self.assertRaises(self._tk.ObjectNotFound, auth.resource_show, context, {})
        else:
            result = auth.resource_show(context, {})
            self.assertEquals(authorized_pkg, result['success'])

    def test_package_adquired(self):
        self.assertTrue(auth.package_adquired({}, {}))
