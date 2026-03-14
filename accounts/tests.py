from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from knox.models import AuthToken
from .models import User, UserProfile, ActivityLog


class AccountsTests(APITestCase):
	def test_register_endpoint(self):
		url = reverse('register')
		payload = {
			'username': 'alice',
			'email': 'alice@example.com',
			'password': 'ComplexPass123!',
			'password2': 'ComplexPass123!',
			'first_name': 'Alice',
			'last_name': 'Smith'
		}
		resp = self.client.post(url, payload, format='json')
		self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
		# response should include token and user data
		self.assertIn('token', resp.data)
		self.assertIn('user', resp.data)
		self.assertEqual(resp.data['user']['email'], 'alice@example.com')

	def test_login_endpoint(self):
		# create a user
		user = User.objects.create_user(username='bob', email='bob@example.com', password='BobPass123!')

		url = reverse('login')
		payload = {'email': 'bob@example.com', 'password': 'BobPass123!'}
		resp = self.client.post(url, payload, format='json')
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		# Knox usually returns a token in response.data
		# If present, ensure it's a non-empty string
		if 'token' in resp.data:
			self.assertTrue(isinstance(resp.data['token'], str) and resp.data['token'])

	def test_profile_get_and_update(self):
		user = User.objects.create_user(username='carol', email='carol@example.com', password='CarolPass123!')
		# ensure profile created
		UserProfile.objects.get_or_create(user=user)
		_, token = AuthToken.objects.create(user)

		self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
		url = reverse('profile')
		resp = self.client.get(url)
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(resp.data['user']['email'], 'carol@example.com')

		# update department
		resp = self.client.patch(url, {'department': 'Sales'}, format='json')
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(resp.data['department'], 'Sales')

	def test_change_password_and_relogin(self):
		user = User.objects.create_user(username='dan', email='dan@example.com', password='OldPass123!')
		_, token = AuthToken.objects.create(user)
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)

		url = reverse('change-password')
		payload = {
			'old_password': 'OldPass123!',
			'new_password': 'NewPass123!',
			'confirm_password': 'NewPass123!'
		}
		resp = self.client.post(url, payload, format='json')
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertIn('message', resp.data)

		# logout and try logging in with new password
		self.client.credentials()  # remove token
		login_url = reverse('login')
		login_resp = self.client.post(login_url, {'email': 'dan@example.com', 'password': 'NewPass123!'}, format='json')
		self.assertEqual(login_resp.status_code, status.HTTP_200_OK)

	def test_admin_user_list_detail_and_activity_logs(self):
		# create a normal user and some activity logs
		normal = User.objects.create_user(username='ed', email='ed@example.com', password='EdPass123!')
		ActivityLog.objects.create(user=normal, action='TEST_ACTION', details={'foo': 'bar'})

		# create admin user
		admin = User.objects.create_superuser(username='admin', email='admin@example.com', password='AdminPass123!')
		_, admin_token = AuthToken.objects.create(admin)

		self.client.credentials(HTTP_AUTHORIZATION='Token ' + admin_token)
		list_url = reverse('user-list')
		resp = self.client.get(list_url)
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		# ensure at least the normal user exists
		emails = [u['email'] for u in resp.data['results']]
		self.assertIn('ed@example.com', emails)

		# user detail
		detail_url = reverse('user-detail', args=[str(normal.id)])
		resp = self.client.get(detail_url)
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(resp.data['email'], 'ed@example.com')

		# activity logs
		logs_url = reverse('activity-logs')
		resp = self.client.get(logs_url)
		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		# at least one log should be present
		self.assertTrue(len(resp.data) >= 1)

