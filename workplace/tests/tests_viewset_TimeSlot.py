import json
import pytz

from unittest import mock

from datetime import datetime, timedelta, date, time

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test.utils import override_settings

from blitz_api.factories import UserFactory, AdminFactory
from blitz_api.services import remove_translation_fields

from ..models import Period, TimeSlot, Workplace, Reservation

User = get_user_model()

LOCAL_TIMEZONE = pytz.timezone(settings.TIME_ZONE)


class TimeSlotTests(APITestCase):

    @classmethod
    def setUpClass(cls):
        super(TimeSlotTests, cls).setUpClass()
        cls.client = APIClient()
        cls.user = UserFactory()
        cls.admin = AdminFactory()
        cls.workplace = Workplace.objects.create(
            name="Blitz",
            seats=40,
            details="short_description",
            address_line1="123 random street",
            postal_code="123 456",
            state_province="Random state",
            country="Random country",
        )
        cls.workplace2 = Workplace.objects.create(
            name="Blitz2",
            seats=40,
            details="short_description",
            address_line1="123 random street",
            postal_code="123 456",
            state_province="Random state",
            country="Random country",
        )
        cls.period = Period.objects.create(
            name="random_period",
            workplace=cls.workplace,
            start_date=LOCAL_TIMEZONE.localize(datetime(2130, 1, 1, 1)),
            end_date=LOCAL_TIMEZONE.localize(datetime(2130, 12, 12, 12)),
            price=3,
            is_active=False,
        )
        cls.period_active = Period.objects.create(
            name="random_period_active",
            workplace=cls.workplace2,
            start_date=LOCAL_TIMEZONE.localize(datetime(2130, 1, 1, 1)),
            end_date=LOCAL_TIMEZONE.localize(datetime(2130, 12, 12, 12)),
            price=3,
            is_active=True,
        )
        cls.period_no_workplace = Period.objects.create(
            name="random_period_active",
            start_date=LOCAL_TIMEZONE.localize(datetime(2130, 1, 1, 1)),
            end_date=LOCAL_TIMEZONE.localize(datetime(2130, 12, 12, 12)),
            price=3,
            is_active=True,
        )
        cls.time_slot = TimeSlot.objects.create(
            name="morning_time_slot",
            period=cls.period,
            price=3,
            start_time=LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 8)),
            end_time=LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 12)),
        )
        cls.reservation = Reservation.objects.create(
            user=cls.user,
            timeslot=cls.time_slot,
            is_active=True,
        )
        cls.reservation_admin = Reservation.objects.create(
            user=cls.admin,
            timeslot=cls.time_slot,
            is_active=True,
        )
        cls.time_slot_active = TimeSlot.objects.create(
            name="evening_time_slot_active",
            period=cls.period_active,
            price=3,
            start_time=LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 18)),
            end_time=LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 22)),
        )

    def test_create(self):
        """
        Ensure we can create a timeslot if user has permission.
        If the period is not assigned to a workplace, places_remaining should
        be 0.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': reverse(
                'period-detail', args=[self.period_no_workplace.id]
            ),
            'price': '10.00',  # Will use Period's price if not provided
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 12)),
            'end_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 16)),
        }

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        content = {
            'id': 3,
            'end_time': data['end_time'].isoformat(),
            'price': '10.00',
            'places_remaining': 0,
            'reservations': [],
            'reservations_canceled': [],
            'start_time': data['start_time'].isoformat(),
            'url': 'http://testserver/time_slots/3',
            'period': 'http://testserver/periods/3',
            'users': [],
            'workplace': None
        }

        self.assertEqual(
            remove_translation_fields(json.loads(response.content)),
            content
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_no_price(self):
        """
        Ensure we can create a timeslot without providing a price.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': reverse('period-detail', args=[self.period.id]),
            # 'price': '10.00',  # Will use Period's price if not provided
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 12)),
            'end_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 16)),
        }

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        response_data = remove_translation_fields(json.loads(response.content))
        response_data['workplace'] = remove_translation_fields(
            response_data['workplace']
        )

        content = {
            'id': 3,
            'end_time': data['end_time'].isoformat(),
            'price': '3.00',
            'places_remaining': 40,
            'reservations': [],
            'reservations_canceled': [],
            'start_time': data['start_time'].isoformat(),
            'url': 'http://testserver/time_slots/3',
            'period': 'http://testserver/periods/1',
            'users': [],
            'workplace': {
                'address_line1': '123 random street',
                'address_line2': None,
                'city': '',
                'country': 'Random country',
                'details': 'short_description',
                'id': 1,
                'latitude': None,
                'longitude': None,
                'name': 'Blitz',
                'pictures': [],
                'postal_code': '123 456',
                'seats': 40,
                'state_province': 'Random state',
                'timezone': None,
                'place_name': '',
                'volunteers': [],
                'url': 'http://testserver/workplaces/1',
            }
        }

        self.assertEqual(response_data, content)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_without_permission(self):
        """
        Ensure we can't create a timeslot if user has no permission.
        """
        self.client.force_authenticate(user=self.user)

        data = {
            'period': reverse('period-detail', args=[self.period.id]),
            # 'price': '10.00',  # Will use Period's price if not provided
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 12)),
            'end_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 16)),
        }

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        content = {
            'detail': 'You do not have permission to perform this action.'
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_overlapping(self):
        """
        Ensure we can't create overlapping timeslot in the same period.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': reverse('period-detail', args=[self.period.id]),
            'price': '10.00',  # Will use Period's price if not provided
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 11)),
            'end_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 15)),
        }

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        content = {
            'detail': [
                'An existing timeslot overlaps with the provided start_time '
                'and end_time.'
            ]
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_invalid_start_end(self):
        """
        Ensure we can't create timeslots with start_time greater than end_time.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': reverse('period-detail', args=[self.period.id]),
            'price': '10.00',  # Will use Period's price if not provided
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 14)),
            'end_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 10)),
        }

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        content = {
            'end_time': ['End time must be later than start_time.'],
            'start_time': ['Start time must be earlier than end_time.']
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_not_within_period(self):
        """
        Ensure we can't create timeslots with start_time or end_time that are
        not with the period's start_date and end_date.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': reverse('period-detail', args=[self.period.id]),
            'price': '10.00',  # Will use Period's price if not provided
            'start_time': LOCAL_TIMEZONE.localize(datetime(3000, 1, 16, 8)),
            'end_time': LOCAL_TIMEZONE.localize(datetime(3000, 1, 16, 12)),
        }

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        content = {
            'start_time': [
                "Start time must be set within the period's start_date and "
                "end_date."
            ]
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data['start_time'] = self.period.start_date

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        content = {
            'end_time': [
                "End time must be set within the period's start_date and "
                "end_date."
            ]
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_inconsistent_day(self):
        """
        Ensure we can't create timeslots with start_time and end_time in
        different days.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': reverse('period-detail', args=[self.period.id]),
            'price': '10.00',  # Will use Period's price if not provided
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 14)),
            'end_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 16, 10)),
        }

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        content = {
            'end_time': ['End time must be the same day as start_time.'],
            'start_time': ['Start time must be the same day as end_time.']
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_non_existent_period(self):
        """
        Ensure we can't create a timeslot with a non-existent user.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': reverse('period-detail', args=[999]),
            # 'price': '10.00',  # Will use Period's price if not provided
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 12)),
            'end_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 16)),
        }

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        content = {
            'period': ['Invalid hyperlink - Object does not exist.'],
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_missing_field(self):
        """
        Ensure we can't create a timeslot when required field are missing.
        """
        self.client.force_authenticate(user=self.admin)

        data = {}

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        content = {
            'end_time': ['This field is required.'],
            'period': ['This field is required.'],
            'start_time': ['This field is required.']
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_blank_field(self):
        """
        Ensure we can't create a timeslot when required field are blank.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': None,
            'price': None,  # Will use Period's price if not provided
            'start_time': None,
            'end_time': None,
        }

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        content = {
            'end_time': ['This field may not be null.'],
            'period': ['This field may not be null.'],
            'start_time': ['This field may not be null.']
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_invalid_field(self):
        """
        Ensure we can't create a timeslot when required field are invalid.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': "123",
            'price': "",  # Will use Period's price if not provided
            'start_time': "",
            'end_time': "",
        }

        response = self.client.post(
            reverse('timeslot-list'),
            data,
            format='json',
        )

        content = {
            'end_time': [
                'Datetime has wrong format. Use one of these formats instead: '
                'YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z].'
            ],
            'period': ['Invalid hyperlink - No URL match.'],
            'price': ['A valid number is required.'],
            'start_time': [
                'Datetime has wrong format. Use one of these formats instead: '
                'YYYY-MM-DDThh:mm[:ss[.uuuuuu]][+HH:MM|-HH:MM|Z].'
            ]
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update(self):
        """
        Ensure we can fully update a timeslot without users.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': reverse('period-detail', args=[self.period.id]),
            'price': '10.00',  # Will use Period's price if not provided
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 12)),
            'end_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 16)),
        }

        response = self.client.put(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 2},
            ),
            data,
            format='json',
        )
        response_data = json.loads(response.content)
        response_data['workplace'] = remove_translation_fields(
            response_data['workplace']
        )

        content = {
            'id': 2,
            'end_time': data['end_time'].isoformat(),
            'price': '10.00',
            'places_remaining': 40,
            'reservations': [],
            'reservations_canceled': [],
            'start_time': data['start_time'].isoformat(),
            'url': 'http://testserver/time_slots/2',
            'period': 'http://testserver/periods/1',
            'users': [],
            "workplace": {
                "address_line1": "123 random street",
                "address_line2": None,
                "city": "",
                "country": "Random country",
                "details": "short_description",
                "id": 1,
                "latitude": None,
                "longitude": None,
                "name": "Blitz",
                "pictures": [],
                "postal_code": "123 456",
                "seats": 40,
                "state_province": "Random state",
                "timezone": None,
                'place_name': '',
                "volunteers": [],
                "url": "http://testserver/workplaces/1"
            }
        }

        self.assertEqual(response_data, content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(
        LOCAL_SETTINGS={
            "EMAIL_SERVICE": True,
        }
    )
    def test_update_timeslot_with_registered_users(self):
        """
        Ensure we can fully update a timeslot with registered users.
        To work properly, the email service needs to be activated and a field
        'force_update' equal to True needs to be passed in the request.
        A 'custom_message' field will be passed to the email template that
        is sent to affected users.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': reverse('period-detail', args=[self.period.id]),
            'price': '10.00',  # Will use Period's price if not provided
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 12)),
            'end_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 16)),
            'force_update': True,
            'custom_message': "This explains the cancellation.",
        }

        response = self.client.put(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 1},
            ),
            data,
            format='json',
        )

        response_data = json.loads(response.content)
        response_data['workplace'] = remove_translation_fields(
            response_data['workplace']
        )

        content = {
            'id': 1,
            'end_time': data['end_time'].isoformat(),
            'price': '10.00',
            'places_remaining': 40,
            'reservations': [],
            'reservations_canceled': [
                'http://testserver/reservations/1',
                'http://testserver/reservations/2'
            ],
            'start_time': data['start_time'].isoformat(),
            'url': 'http://testserver/time_slots/1',
            'period': 'http://testserver/periods/1',
            'users': [
                'http://testserver/users/1',
                'http://testserver/users/2'
            ],
            "workplace": {
                "address_line1": "123 random street",
                "address_line2": None,
                "city": "",
                "country": "Random country",
                "details": "short_description",
                "id": 1,
                "latitude": None,
                "longitude": None,
                "name": "Blitz",
                "pictures": [],
                "postal_code": "123 456",
                "seats": 40,
                "state_province": "Random state",
                "timezone": None,
                'place_name': '',
                "volunteers": [],
                "url": "http://testserver/workplaces/1"
            }
        }

        self.assertEqual(response_data, content)

        self.reservation.refresh_from_db()

        self.assertFalse(self.reservation.is_active)
        self.assertEqual(self.reservation.cancelation_reason, 'TM')
        self.assertTrue(self.reservation.cancelation_date)

        self.reservation.is_active = True
        self.reservation.cancelation_date = None
        self.reservation.cancelation_reason = None
        self.reservation.save()
        self.reservation.refresh_from_db()

        user = self.user
        user.refresh_from_db()

        self.assertEqual(user.tickets, 2)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test that two messages were sent:
        self.assertEqual(len(mail.outbox), 2)

    @mock.patch('blitz_api.services.EmailMessage.send', return_value=0)
    def test_update_safe(self, send):
        """
        Ensure we can partially update a timeslot with registered users if
        start_time and end_time are not modified.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'price': '1000.00',
            'force_update': True,
        }

        response = self.client.patch(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 1},
            ),
            data,
            format='json',
        )

        response_data = json.loads(response.content)
        response_data['workplace'] = remove_translation_fields(
            response_data['workplace']
        )

        content = {
            'id': 1,
            'end_time': response_data['end_time'],
            'price': '1000.00',
            'places_remaining': 38,
            'reservations': [
                'http://testserver/reservations/1',
                'http://testserver/reservations/2'
            ],
            'reservations_canceled': [],
            'start_time': response_data['start_time'],
            'url': 'http://testserver/time_slots/1',
            'period': 'http://testserver/periods/1',
            'users': [
                'http://testserver/users/1',
                'http://testserver/users/2'
            ],
            "workplace": {
                "address_line1": "123 random street",
                "address_line2": None,
                "city": "",
                "country": "Random country",
                "details": "short_description",
                "id": 1,
                "latitude": None,
                "longitude": None,
                "name": "Blitz",
                "pictures": [],
                "postal_code": "123 456",
                "seats": 40,
                "state_province": "Random state",
                "timezone": None,
                'place_name': '',
                "volunteers": [],
                "url": "http://testserver/workplaces/1"
            }
        }

        self.assertEqual(response_data, content)

        self.reservation.refresh_from_db()
        self.assertTrue(self.reservation.is_active)
        self.assertFalse(self.reservation.cancelation_reason)
        self.assertFalse(self.reservation.cancelation_date)

        user = self.user
        user.refresh_from_db()

        self.assertEqual(user.tickets, 1)

        # Test that no message was sent:
        self.assertEqual(len(mail.outbox), 0)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # @override_settings(
    #     LOCAL_SETTINGS={
    #         "EMAIL_SERVICE": False,
    #         "FRONTEND_INTEGRATION": {
    #             "FORGOT_PASSWORD_URL": "fake_url",
    #         }
    #     }
    # )
    # def test_update_email_disabled(self):
    #     """
    #     Ensure we can't update a timeslot start_time or end_time if email
    #     service is disabled.
    #     """
    #     self.client.force_authenticate(user=self.admin)
    #
    #     data = {
    #         'period': reverse('period-detail', args=[self.period.id]),
    #         'price': '10.00',  # Will use Period's price if not provided
    #         'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 12)),
    #         'end_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 16)),
    #         'force_update': True,
    #     }
    #
    #     response = self.client.put(
    #         reverse(
    #             'timeslot-detail',
    #             kwargs={'pk': 1},
    #         ),
    #         data,
    #         format='json',
    #     )
    #
    #     content = {
    #         'detail': 'Email service is disabled.'
    #     }
    #
    #     self.assertEqual(json.loads(response.content), content)
    #
    #     self.assertEqual(
    #         response.status_code,
    #         status.HTTP_500_INTERNAL_SERVER_ERROR,
    #     )

    def test_update_not_force(self):
        """
        Ensure we can't update a timeslot start_time or end_time if the field
        "force_update" is not provided.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'period': reverse('period-detail', args=[self.period.id]),
            'price': '10.00',  # Will use Period's price if not provided
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 12)),
            'end_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 16)),
        }

        response = self.client.put(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 1},
            ),
            data,
            format='json',
        )

        content = {
            'non_field_errors': [
                'Trying to push an update that affects users without '
                'providing `force_update` field.'
            ]
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    @override_settings(
        LOCAL_SETTINGS={
            "EMAIL_SERVICE": True,
        }
    )
    def test_update_timeslot_with_registered_users_partial(self):
        """
        Ensure we can partially update a timeslot.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'price': '1000.00',
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 6)),
            'force_update': True,
        }

        response = self.client.patch(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 1},
            ),
            data,
            format='json',
        )

        response_data = json.loads(response.content)
        response_data['workplace'] = remove_translation_fields(
            response_data['workplace']
        )

        content = {
            'id': 1,
            'end_time': response_data['end_time'],
            'price': '1000.00',
            'places_remaining': 40,
            'reservations': [],
            'reservations_canceled': [
                'http://testserver/reservations/1',
                'http://testserver/reservations/2'
            ],
            'start_time': data['start_time'].isoformat(),
            'url': 'http://testserver/time_slots/1',
            'period': 'http://testserver/periods/1',
            'users': [
                'http://testserver/users/1',
                'http://testserver/users/2'
            ],
            "workplace": {
                "address_line1": "123 random street",
                "address_line2": None,
                "city": "",
                "country": "Random country",
                "details": "short_description",
                "id": 1,
                "latitude": None,
                "longitude": None,
                "name": "Blitz",
                "pictures": [],
                "postal_code": "123 456",
                "seats": 40,
                "state_province": "Random state",
                "timezone": None,
                'place_name': '',
                "volunteers": [],
                "url": "http://testserver/workplaces/1"
            }
        }

        self.assertEqual(response_data, content)

        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_active)
        self.assertEqual(self.reservation.cancelation_reason, 'TM')
        self.assertTrue(self.reservation.cancelation_date)

        self.reservation.is_active = True
        self.reservation.cancelation_date = None
        self.reservation.cancelation_reason = None
        self.reservation.save()
        self.reservation.refresh_from_db()

        user = self.user
        user.refresh_from_db()

        self.assertEqual(user.tickets, 2)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test that two message was sent:
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(
        LOCAL_SETTINGS={
            "EMAIL_SERVICE": True,
        }
    )
    @mock.patch('blitz_api.services.EmailMessage.send', return_value=0)
    def test_update_timeslot_failed_emails(self, send):
        """
        Ensure we can partially update a timeslot, even if we were unable to
        deliver emails to affected users.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'price': '1000.00',
            'start_time': LOCAL_TIMEZONE.localize(datetime(2130, 1, 15, 6)),
            'force_update': True,
        }

        response = self.client.patch(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 1},
            ),
            data,
            format='json',
        )

        response_data = json.loads(response.content)
        response_data['workplace'] = remove_translation_fields(
            response_data['workplace']
        )

        content = {
            'id': 1,
            'end_time': response_data['end_time'],
            'price': '1000.00',
            'places_remaining': 40,
            'reservations': [],
            'reservations_canceled': [
                'http://testserver/reservations/1',
                'http://testserver/reservations/2'
            ],
            'start_time': data['start_time'].isoformat(),
            'url': 'http://testserver/time_slots/1',
            'period': 'http://testserver/periods/1',
            'users': [
                'http://testserver/users/1',
                'http://testserver/users/2'
            ],
            "workplace": {
                "address_line1": "123 random street",
                "address_line2": None,
                "city": "",
                "country": "Random country",
                "details": "short_description",
                "id": 1,
                "latitude": None,
                "longitude": None,
                "name": "Blitz",
                "pictures": [],
                "postal_code": "123 456",
                "seats": 40,
                "state_province": "Random state",
                "timezone": None,
                'place_name': '',
                "volunteers": [],
                "url": "http://testserver/workplaces/1"
            }
        }

        self.assertEqual(response_data, content)

        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.is_active)
        self.assertEqual(self.reservation.cancelation_reason, 'TM')
        self.assertTrue(self.reservation.cancelation_date)

        user = self.user
        user.refresh_from_db()

        self.assertEqual(user.tickets, 2)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test that no email was sent:
        self.assertEqual(len(mail.outbox), 0)

    def test_delete(self):
        """
        Ensure we can delete a timeslot that has no reservations.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'custom_message': None
        }

        response = self.client.delete(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 2},
            ),
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_with_reservations(self):
        """
        Ensure we can delete a timeslot that has reservations.
        """
        self.client.force_authenticate(user=self.admin)

        reservation_2 = Reservation.objects.create(
            user=self.user,
            timeslot=self.time_slot,
            is_active=True,
        )

        data = {
            'force_delete': True,
        }

        response = self.client.delete(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 1},
            ),
            data,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.reservation.refresh_from_db()
        self.user.refresh_from_db()
        self.admin.refresh_from_db()

        self.assertFalse(self.reservation.is_active)
        self.assertEqual(self.reservation.cancelation_reason, 'TD')
        self.assertTrue(self.reservation.cancelation_date)
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(self.user.tickets, 3)
        self.assertEqual(self.admin.tickets, 2)

        self.reservation.is_active = True
        self.reservation.cancelation_date = None
        self.reservation.cancelation_reason = None
        self.reservation.save()
        self.reservation.refresh_from_db()
        reservation_2.delete()
        self.user.tickets = 1
        self.user.save()
        self.admin.tickets = 1
        self.admin.save()

    def test_delete_with_reservations_no_force(self):
        """
        Ensure we can't delete a timeslot that has reservations if the
        force_delete field is not provided and set to True.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            # 'force_delete': True,
        }

        response = self.client.delete(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 1},
            ),
            data,
            format='json',
        )

        content = {
            "non_field_errors": [
                "Trying to do a TimeSlot deletion that affects "
                "users without providing `force_delete` field set to True."
            ]
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_with_reservations_invalid_force_delete(self):
        """
        Ensure we can't delete a timeslot that has reservations if the
        force_delete field is not provided and set to True.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            'force_delete': "invalid",
        }

        response = self.client.delete(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 1},
            ),
            data,
            format='json',
        )

        content = {
            'force_delete': [
                'Must be a valid boolean.'
            ]
        }

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(json.loads(response.content), content)

    def test_list(self):
        """
        Ensure we can list active timeslots as an unauthenticated user.
        """
        response = self.client.get(
            reverse('timeslot-list'),
            format='json',
        )

        data = json.loads(response.content)
        for idx, obj in enumerate(data['results']):
            data['results'][idx]['workplace'] = remove_translation_fields(
                obj['workplace']
            )

        content = {
            'count': 1,
            'next': None,
            'previous': None,
            'results': [{
                'id': 2,
                'end_time': data['results'][0]['end_time'],
                'price': '3.00',
                'places_remaining': 40,
                'reservations': [],
                'reservations_canceled': [],
                'start_time': data['results'][0]['start_time'],
                'url': 'http://testserver/time_slots/2',
                'period': 'http://testserver/periods/2',
                'users': [],
                "workplace": {
                    "address_line1": "123 random street",
                    "address_line2": None,
                    "city": "",
                    "country": "Random country",
                    "details": "short_description",
                    "id": 2,
                    "latitude": None,
                    "longitude": None,
                    "name": "Blitz2",
                    "pictures": [],
                    "postal_code": "123 456",
                    "seats": 40,
                    "state_province": "Random state",
                    "timezone": None,
                    "place_name": '',
                    "volunteers": [],
                    "url": "http://testserver/workplaces/2"
                }
            }]
        }

        self.assertEqual(data, content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_inactive(self):
        """
        Ensure we can list all timeslots as an admin user.
        """
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            reverse('timeslot-list'),
            format='json',
        )

        data = json.loads(response.content)
        for idx, obj in enumerate(data['results']):
            data['results'][idx]['workplace'] = remove_translation_fields(
                obj['workplace']
            )

        content = {
            'count': 2,
            'next': None,
            'previous': None,
            'results': [{
                'id': 1,
                'end_time': data['results'][0]['end_time'],
                'period': 'http://testserver/periods/1',
                'price': '3.00',
                'places_remaining': 38,
                'reservations': [
                    'http://testserver/reservations/1',
                    'http://testserver/reservations/2'
                ],
                'reservations_canceled': [],
                'start_time': data['results'][0]['start_time'],
                'url': 'http://testserver/time_slots/1',
                'users': [
                    'http://testserver/users/1',
                    'http://testserver/users/2'
                ],
                "workplace": {
                    "address_line1": "123 random street",
                    "address_line2": None,
                    "city": "",
                    "country": "Random country",
                    "details": "short_description",
                    "id": 1,
                    "latitude": None,
                    "longitude": None,
                    "name": "Blitz",
                    "pictures": [],
                    "postal_code": "123 456",
                    "seats": 40,
                    "state_province": "Random state",
                    "timezone": None,
                    "place_name": '',
                    "volunteers": [],
                    "url": "http://testserver/workplaces/1"
                }
            }, {
                'id': 2,
                'end_time': data['results'][1]['end_time'],
                'price': '3.00',
                'places_remaining': 40,
                'reservations': [],
                'reservations_canceled': [],
                'start_time': data['results'][1]['start_time'],
                'url': 'http://testserver/time_slots/2',
                'period': 'http://testserver/periods/2',
                'users': [],
                "workplace": {
                    "address_line1": "123 random street",
                    "address_line2": None,
                    "city": "",
                    "country": "Random country",
                    "details": "short_description",
                    "id": 2,
                    "latitude": None,
                    "longitude": None,
                    "name": "Blitz2",
                    "pictures": [],
                    "postal_code": "123 456",
                    "seats": 40,
                    "state_province": "Random state",
                    "timezone": None,
                    "place_name": '',
                    "volunteers": [],
                    "url": "http://testserver/workplaces/2"
                }
            }]
        }

        self.assertEqual(data, content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_filter_by_workplace(self):
        """
        Ensure we can list all timeslots linked to a workplace.
        """
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            reverse('timeslot-list') + "?period__workplace=1",
            format='json',
        )

        data = json.loads(response.content)
        for idx, obj in enumerate(data['results']):
            data['results'][idx]['workplace'] = remove_translation_fields(
                obj['workplace']
            )

        content = {
            'count': 1,
            'next': None,
            'previous': None,
            'results': [{
                'id': 1,
                'end_time': data['results'][0]['end_time'],
                'period': 'http://testserver/periods/1',
                'places_remaining': 38,
                'reservations': [
                    'http://testserver/reservations/1',
                    'http://testserver/reservations/2'
                ],
                'reservations_canceled': [],
                'price': '3.00',
                'start_time': data['results'][0]['start_time'],
                'url': 'http://testserver/time_slots/1',
                'users': [
                    'http://testserver/users/1',
                    'http://testserver/users/2'
                ],
                "workplace": {
                    "address_line1": "123 random street",
                    "address_line2": None,
                    "city": "",
                    "country": "Random country",
                    "details": "short_description",
                    "id": 1,
                    "latitude": None,
                    "longitude": None,
                    "name": "Blitz",
                    "pictures": [],
                    "postal_code": "123 456",
                    "seats": 40,
                    "state_province": "Random state",
                    "timezone": None,
                    "place_name": '',
                    "volunteers": [],
                    "url": "http://testserver/workplaces/1"
                }
            }]
        }

        self.assertEqual(data, content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_filter_not_overiding_active(self):
        """
        Ensure we can list all timeslots linked to a workplace without
        overriding is_active default filtering.
        """
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse('timeslot-list') + "?period__workplace=1",
            format='json',
        )

        data = json.loads(response.content)

        content = {
            'count': 0,
            'next': None,
            'previous': None,
            'results': []
        }

        self.assertEqual(data, content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_read(self):
        """
        Ensure we can read a timeslot as an unauthenticated user if it is
        active.
        """

        response = self.client.get(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 2},
            ),
        )

        data = json.loads(response.content)

        content = {
            'id': 2,
            'end_time': data['end_time'],
            'price': '3.00',
            'places_remaining': 40,
            'reservations': [],
            'reservations_canceled': [],
            'start_time': data['start_time'],
            'url': 'http://testserver/time_slots/2',
            'period': 'http://testserver/periods/2',
            'users': [],
            "workplace": {
                "address_line1": "123 random street",
                "address_line2": None,
                "city": "",
                "country": "Random country",
                "details": "short_description",
                "id": 2,
                "latitude": None,
                "longitude": None,
                "name": "Blitz2",
                "pictures": [],
                "postal_code": "123 456",
                "seats": 40,
                "state_province": "Random state",
                "timezone": None,
                "place_name": '',
                "volunteers": [],
                "url": "http://testserver/workplaces/2"
            }
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_read_inactive_non_admin(self):
        """
        Ensure we can't read a timeslot as non_admin if it is inactive.
        """

        response = self.client.get(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 1},
            ),
        )

        content = {'detail': 'Not found.'}

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_read_inactive(self):
        """
        Ensure we can read a timeslot as admin if it is inactive.
        """
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 1},
            ),
        )

        data = json.loads(response.content)
        data['workplace'] = remove_translation_fields(
            data['workplace']
        )
        data['users'] = [
            remove_translation_fields(u) for u in data['users']
        ]

        content = {
            'id': 1,
            'end_time': data['end_time'],
            'period': 'http://testserver/periods/1',
            'price': '3.00',
            'places_remaining': 38,
            'reservations': [
                'http://testserver/reservations/1',
                'http://testserver/reservations/2'
            ],
            'reservations_canceled': [],
            'start_time': data['start_time'],
            'url': 'http://testserver/time_slots/1',
            'users': [{
                "academic_field": None,
                "academic_level": None,
                "birthdate": None,
                "date_joined": data['users'][0]['date_joined'],
                "email": data['users'][0]['email'],
                "first_name": data['users'][0]['first_name'],
                "gender": None,
                "groups": [],
                "id": 1,
                "is_active": True,
                "is_staff": False,
                "is_superuser": False,
                "last_login": None,
                "last_name": data['users'][0]['last_name'],
                "membership": None,
                "membership_end": None,
                "other_phone": None,
                "phone": None,
                "tickets": 1,
                "university": None,
                "url": "http://testserver/users/1",
                "user_permissions": [],
                'city': None,
                'personnal_restrictions': None,
                'academic_program_code': None,
                'faculty': None,
                'student_number': None,
                'volunteer_for_workplace': [],
                }, data['users'][1]
            ],
            "workplace": {
                "address_line1": "123 random street",
                "address_line2": None,
                "city": "",
                "country": "Random country",
                "details": "short_description",
                "id": 1,
                "latitude": None,
                "longitude": None,
                "name": "Blitz",
                "pictures": [],
                "postal_code": "123 456",
                "seats": 40,
                "state_province": "Random state",
                "timezone": None,
                "place_name": '',
                "volunteers": [],
                "url": "http://testserver/workplaces/1"
            }
        }

        self.assertEqual(data, content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_read_non_existent(self):
        """
        Ensure we get not found when asking for a period that doesn't exist.
        """

        response = self.client.get(
            reverse(
                'timeslot-detail',
                kwargs={'pk': 999},
            ),
        )

        content = {'detail': 'Not found.'}

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_batch_create(self):
        """
        Ensure that an admin can batch create timeslots for a specific period.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            "period": reverse(
                'period-detail', args=[self.period_no_workplace.id]
            ),
            "name": "test",  # Optional
            "start_time": "08:00:00",
            "end_time": "12:00:00",
            "start_date": "2130-01-01",
            "end_date": "2130-12-12",
            "weekdays": [0, 1, 2, 3, 4, 5, 6],
        }

        response = self.client.post(
            reverse('timeslot-batch-create'),
            data,
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.content
        )

        new_timeslots = TimeSlot.objects.filter(
            period=self.period_no_workplace
        )
        new_timeslot_count = new_timeslots.count()

        start_date = date(2130, 1, 1)
        end_date = date(2130, 12, 12)

        nb_timeslot = (end_date - start_date).days

        self.assertEqual(
            new_timeslot_count,
            nb_timeslot + 1,
            "Bad timeslot count"
        )

        # Verify time for every timeslot
        # This is to make sure that there are no variations due to DST
        # Timezone is America/Monrteal since no workplace is associated with
        # the provided period.
        for timeslot in new_timeslots:
            self.assertEqual(
                timeslot.start_time.astimezone(
                    pytz.timezone("America/Montreal")).time(),
                time(8, 0, 0)
            )
            self.assertEqual(
                timeslot.end_time.astimezone(
                    pytz.timezone("America/Montreal")).time(),
                time(12, 0, 0)
            )

    def test_batch_create_without_permission(self):
        """
        Ensure that an admin can batch create timeslots for a specific period.
        """
        self.client.force_authenticate(user=self.user)

        data = {
            "period": reverse(
                'period-detail', args=[self.period_no_workplace.id]
            ),
            "start_time": "08:00:00",
            "end_time": "12:00:00",
            "start_date": "2012-01-01",
            "end_date": "2012-01-01",
            "weekdays": [1, 2, 3, ],
        }

        response = self.client.post(
            reverse('timeslot-batch-create'),
            data,
            format='json',
        )

        content = {
            'detail': 'You do not have permission to perform this action.'
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_batch_create_duplicate_weekdays(self):
        """
        Ensure that an admin can't batch create when weekdays are duplicated.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            "period": reverse(
                'period-detail', args=[self.period_no_workplace.id]
            ),
            "name": "test",
            "start_time": "08:00:00",
            "end_time": "12:00:00",
            "start_date": "2012-01-01",
            "end_date": "2012-01-01",
            "weekdays": [1, 2, 3, 3, ],
        }

        response = self.client.post(
            reverse('timeslot-batch-create'),
            data,
            format='json',
        )

        content = {
            "weekdays": [
                "Duplicated weekdays are not authorized."
            ]
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_create_bad_weekdays(self):
        """
        Ensure that an admin can't batch create when weekdays are incorrect.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            "period": reverse(
                'period-detail', args=[self.period_no_workplace.id]
            ),
            "name": "test",
            "start_time": "08:00:00",
            "end_time": "12:00:00",
            "start_date": "2012-01-01",
            "end_date": "2012-01-01",
            "weekdays": [1, 2, 3, 9, ],
        }

        response = self.client.post(
            reverse('timeslot-batch-create'),
            data,
            format='json',
        )

        content = {
            "weekdays": {
                "3": [  # Element at position 3 is bad
                    "Ensure this value is less than or equal to 6."
                ]
            }
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_create_duplicate_timeslot(self):
        """
        Ensure that an admin can't batch create when existing timeslots
        overlap with the one we try to batch create.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            "period": reverse(
                'period-detail', args=[self.period_active.id]
            ),
            "name": "test",
            "start_date": "2130-01-15",
            "end_date": "2130-02-15",
            "start_time": "00:00:00",
            "end_time": "23:59:59",
            "weekdays": [0, 1, 2, 3, 4, 5, 6],
        }

        response = self.client.post(
            reverse('timeslot-batch-create'),
            data,
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            response.content,
        )

        content = {
            "non_field_errors": [
                "An existing timeslot overlaps with the provided start_time "
                "and end_time."
            ]
        }

        self.assertEqual(json.loads(response.content), content)

    def test_batch_create_bad_dates(self):
        """
        Ensure that an admin can't batch create when dates do not respect
        period boundaries.
        """
        self.client.force_authenticate(user=self.admin)

        data = {
            "period": reverse(
                'period-detail', args=[self.period_no_workplace.id]
            ),
            "name": "test",
            "start_time": "08:00:00",
            "end_time": "12:00:00",
            "start_date": "2012-01-01",
            "end_date": "2012-01-01",
            "weekdays": [1, 2, 3, ],
        }

        response = self.client.post(
            reverse('timeslot-batch-create'),
            data,
            format='json',
        )

        content = {
            'start_date': [
                "Start date must be set within the period's start_date and "
                'end_date.'
            ]
        }

        self.assertEqual(json.loads(response.content), content)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
