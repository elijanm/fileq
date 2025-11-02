from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from typing import Any, Dict, List, Text
import re

class ActionSetRole(Action):
    def name(self) -> Text:
        return "action_set_role"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        latest_message = tracker.latest_message.get('text', '').strip()
        
        role_mapping = {
            '1': 'caregiver',
            'caregiver': 'caregiver',
            'I am a caregiver': 'caregiver',
            '2': 'afh_provider', 
            'afh provider': 'afh_provider',
            'I run an AFH': 'afh_provider',
            '3': 'service_provider',
            'service provider': 'service_provider',
            'I provide services': 'service_provider'
        }
        
        user_role = role_mapping.get(latest_message.lower())
        
        if user_role:
            return [SlotSet("user_role", user_role)]
        
        return []

class ActionCheckRegistration(Action):
    def name(self) -> Text:
        return "action_check_registration"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        latest_message = tracker.latest_message.get('text', '')
        
        phone_pattern = r'\(?[0-9]{3}\)?[-\s]?[0-9]{3}[-\s]?[0-9]{4}'
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        contact_info = None
        if re.search(phone_pattern, latest_message):
            contact_info = re.search(phone_pattern, latest_message).group()
        elif re.search(email_pattern, latest_message):
            contact_info = re.search(email_pattern, latest_message).group()
        
        # Simple registration check
        known_contacts = ['206-555-0000', 'admin@afhsync.com']
        is_registered = contact_info in known_contacts
        
        return [
            SlotSet("contact_info", contact_info),
            SlotSet("is_registered", is_registered)
        ]

class ActionHandleCertificationSelection(Action):
    def name(self) -> Text:
        return "action_handle_certification_selection"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        latest_message = tracker.latest_message.get('text', '').strip()
        
        # Map certification selections
        cert_mapping = {
            '1': 'CNA (Certified Nursing Assistant)',
            '2': 'HCA (Home Care Aide)', 
            '3': 'RN (Registered Nurse)',
            '4': 'CPR Certified',
            '5': 'First Aid Certified',
            '6': 'Other/None',
            'cna': 'CNA (Certified Nursing Assistant)',
            'hca': 'HCA (Home Care Aide)',
            'rn': 'RN (Registered Nurse)',
            'cpr': 'CPR Certified',
            'first aid': 'First Aid Certified'
        }
        
        selected_cert = cert_mapping.get(latest_message.lower())
        
        if selected_cert:
            return [SlotSet("selected_credentials", selected_cert)]
        
        return []

class ActionHandleUploadPreference(Action):
    def name(self) -> Text:
        return "action_handle_upload_preference"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        latest_message = tracker.latest_message.get('text', '').strip().lower()
        
        if 'now' in latest_message:
            dispatcher.utter_message(response="utter_upload_now")
            return [SlotSet("upload_timing", "now")]
        elif 'later' in latest_message:
            dispatcher.utter_message(response="utter_upload_later")
            return [SlotSet("upload_timing", "later")]
        
        return []

class ActionHandleNotificationPreference(Action):
    def name(self) -> Text:
        return "action_handle_notification_preference"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        latest_message = tracker.latest_message.get('text', '').strip().lower()
        contact_info = tracker.get_slot("contact_info")
        
        # Determine current contact type
        phone_pattern = r'\(?[0-9]{3}\)?[-\s]?[0-9]{3}[-\s]?[0-9]{4}'
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        has_phone = contact_info and re.match(phone_pattern, contact_info)
        has_email = contact_info and re.match(email_pattern, contact_info)
        
        events = []
        
        if 'mobile' in latest_message or 'sms' in latest_message or 'text' in latest_message:
            events.append(SlotSet("notification_method", "mobile"))
            if not has_phone:
                events.append(SlotSet("missing_contact_type", "phone number"))
                dispatcher.utter_message(response="utter_ask_missing_contact")
                return events
        elif 'email' in latest_message:
            events.append(SlotSet("notification_method", "email"))
            if not has_email:
                events.append(SlotSet("missing_contact_type", "email address"))
                dispatcher.utter_message(response="utter_ask_missing_contact")
                return events
        
        return events

class ActionShowServices_old(Action):
    def name(self) -> Text:
        return "action_show_services"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        user_role = tracker.get_slot("user_role")
        is_registered = tracker.get_slot("is_registered")
        
        if not is_registered:
            if user_role == "caregiver":
                dispatcher.utter_message(response="utter_new_user_welcome")
            return []
        
        if user_role == "caregiver":
            dispatcher.utter_message(response="utter_caregiver_services")
        elif user_role == "afh_provider":
            dispatcher.utter_message(response="utter_afh_services")
        elif user_role == "service_provider":
            dispatcher.utter_message(response="utter_service_provider_services")
        
        return []
class ActionShowServices(Action):
    def name(self) -> Text:
        return "action_show_services"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        user_role = tracker.get_slot("user_role")
        is_registered = tracker.get_slot("is_registered")
        
        if not user_role:
            dispatcher.utter_message(text="I'm not sure which role you selected. Please try again.")
            dispatcher.utter_message(response="utter_role_selection")
            return []
        
        if not is_registered:
            dispatcher.utter_message(response="utter_new_user_welcome")
            # NEW: Return FollowupAction to start the form
            from rasa_sdk.events import FollowupAction
            return [FollowupAction("caregiver_registration_form")]
        
        # Show services for returning users
        if user_role == "caregiver":
            dispatcher.utter_message(response="utter_caregiver_services")
        elif user_role == "afh_provider":
            dispatcher.utter_message(response="utter_afh_services")
        elif user_role == "service_provider":
            dispatcher.utter_message(response="utter_service_provider_services")
        
        return []
class ActionGenerateLink(Action):
    def name(self) -> Text:
        return "action_generate_link"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        user_role = tracker.get_slot("user_role")
        contact_info = tracker.get_slot("contact_info")
        location = tracker.get_slot("location")
        availability = tracker.get_slot("availability")
        
        if user_role == "caregiver":
            if location and availability:
                link = f"https://afhsync.com/jobs?location={location}&availability={availability}&contact={contact_info}"
                dispatcher.utter_message(text=f"Here are job opportunities in {location} matching your availability: {link}")
            elif location:
                link = f"https://afhsync.com/jobs?location={location}&contact={contact_info}"
                dispatcher.utter_message(text=f"Here are job opportunities in {location}: {link}")
            else:
                link = f"https://afhsync.com/jobs?contact={contact_info}"
                dispatcher.utter_message(text=f"Here are all available job opportunities: {link}")
        
        elif user_role == "afh_provider":
            link = f"https://afhsync.com/caregivers?contact={contact_info}"
            dispatcher.utter_message(text=f"Browse qualified caregivers: {link}")
        
        elif user_role == "service_provider":
            link = f"https://afhsync.com/afh-requests?contact={contact_info}"
            dispatcher.utter_message(text=f"View AFH service requests: {link}")
        
        return []