# -*- coding: utf-8 -*-

import logging
import requests
import six
import random
import json

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.dispatch_components import (
    AbstractRequestHandler, AbstractExceptionHandler,
    AbstractResponseInterceptor, AbstractRequestInterceptor)
from ask_sdk_core.utils import is_intent_name, is_request_type

from typing import Union, Dict, Any, List
from ask_sdk_model.dialog import (
    ElicitSlotDirective, DelegateDirective)
from ask_sdk_model import (
    Response, IntentRequest, DialogState, SlotConfirmationStatus, Slot)
from ask_sdk_model.slu.entityresolution import StatusCode

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Request Handler classes
class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for skill launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In LaunchRequestHandler")
        speech = ('Hi ! Welcome. I would love to help you in selecting books. What type of books are you looking for?')
        reprompt = "What type of books are you looking for?"
        handler_input.response_builder.speak(speech).ask(reprompt)
        return handler_input.response_builder.response

class InProgressBookMatchIntent(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("BookMatchIntent")(handler_input)
                and handler_input.request_envelope.request.dialog_state != DialogState.COMPLETED)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In InProgressBookMatchIntent")
        current_intent = handler_input.request_envelope.request.intent
        prompt = ""

        for slot_name, current_slot in six.iteritems(
                current_intent.slots):
            if slot_name not in ["bookgenre", "bookAuthor", "I_Want"]:
                if (current_slot.confirmation_status != SlotConfirmationStatus.CONFIRMED
                        and current_slot.resolutions
                        and current_slot.resolutions.resolutions_per_authority[0]):
                    if current_slot.resolutions.resolutions_per_authority[0].status.code == StatusCode.ER_SUCCESS_MATCH:
                        if len(current_slot.resolutions.resolutions_per_authority[0].values) > 1:
                            prompt = "Which would you like "

                            values = " or ".join([e.value.name for e in current_slot.resolutions.resolutions_per_authority[0].values])
                            prompt += values + " ?"
                            return handler_input.response_builder.speak(
                                prompt).ask(prompt).add_directive(
                                ElicitSlotDirective(slot_to_elicit=current_slot.name)
                            ).response
                    elif current_slot.resolutions.resolutions_per_authority[0].status.code == StatusCode.ER_SUCCESS_NO_MATCH:
                        if current_slot.name in required_slots:
                            prompt = "What {} are you looking for?".format(current_slot.name)

                            return handler_input.response_builder.speak(
                                prompt).ask(prompt).add_directive(
                                    ElicitSlotDirective(
                                        slot_to_elicit=current_slot.name
                                    )).response

        return handler_input.response_builder.add_directive(
            DelegateDirective(
                updated_intent=current_intent
            )).response


class CompletedBookMatchIntent(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("BookMatchIntent")(handler_input)
            and handler_input.request_envelope.request.dialog_state == DialogState.COMPLETED)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In CompletedBookMatchIntent")
        filled_slots = handler_input.request_envelope.request.intent.slots
        slot_values = get_slot_values(filled_slots)
        book_match_options = build_book_match_options(
            host_name=book_match_api["host_name"], path=book_match_api["pets"],
            port=book_match_api["port"], slot_values=slot_values)

        try:
            response = http_get(book_match_options)

            if response["result"]:
                speech = ("So  {} "
                          "{} "
                          "{} "
                          "I recommend this book for you. Consider a "
                          "{}".format(
                    slot_values["genre"]["resolved"],
                    slot_values["author"]["resolved"]
                    response["result"][0]["breed"])
                )
            else:
                speech = ("I am sorry I could not find a match for a "
                          "{} "
                          "{} ".format(
                    slot_values["genre"]["resolved"],
                    slot_values["author"]["resolved"]
                )
        except Exception as e:
            speech = ("I am really sorry. I am unable to access part of my "
                      "memory. Please try again later")
            logger.info("Intent: {}: message: {}".format(
                handler_input.request_envelope.request.intent.name, str(e)))

        return handler_input.response_builder.speak(speech).response


class FallbackIntentHandler(AbstractRequestHandler):
    """Handler for handling fallback intent.
     2018-May-01: AMAZON.FallackIntent is only currently available in
     en-US locale. This handler will not be triggered except in that
     locale, so it can be safely deployed for any locale."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In FallbackIntentHandler")
        speech = ("I'm sorry book Match can't help you with that. I can help "
                  "suggest books for you. What types of"
                  "books you are looking for?")
        reprompt = "Please tell me what type of books are you looking for?"
        handler_input.response_builder.speak(speech).ask(reprompt)
        return handler_input.response_builder.response


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for help intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In HelpIntentHandler")
        speech = ("This is suggest a book service. I can suggest books"
                  "for you. You can say, I want fiction books.")
        reprompt = "What type of books are you looking for?"

        handler_input.response_builder.speak(speech).ask(reprompt)
        return handler_input.response_builder.response


class ExitIntentHandler(AbstractRequestHandler):
    """Single Handler for Cancel, Stop and Pause intents."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In ExitIntentHandler")
        handler_input.response_builder.speak("Bye").set_should_end_session(
            True)
        return handler_input.response_builder.response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for skill session end."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In SessionEndedRequestHandler")
        logger.info("Session ended with reason: {}".format(
            handler_input.request_envelope.request.reason))
        return handler_input.response_builder.response

# Exception Handler classes
class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Catch All Exception handler.
    This handler catches all kinds of exceptions and prints
    the stack trace on AWS Cloudwatch with the request envelope."""
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speech = "Sorry, I can't understand the command. Please say again."
        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response


# Request and Response Loggers
class RequestLogger(AbstractRequestInterceptor):
    """Log the request envelope."""
    def process(self, handler_input):
        # type: (HandlerInput) -> None
        logger.info("Request Envelope: {}".format(
            handler_input.request_envelope))


class ResponseLogger(AbstractResponseInterceptor):
    """Log the response envelope."""
    def process(self, handler_input, response):
        # type: (HandlerInput, Response) -> None
        logger.info("Response: {}".format(response))


# Data
required_slots = ["author", "genre"]

slots_meta = {
    "pet": {
        "invalid_responses": [
            "I'm sorry, but I'm not qualified to match you with {}s.",
            "Ah yes, {}s are splendid creatures, but unfortunately owning one as a pet is outlawed.",
            "I'm sorry I can't match you with {}s."
        ]
    },
    "error_default": "I'm sorry I can't match you with {}s."
}

book_match_api = {
    "host_name": "e4v7rdwl7l.execute-api.us-east-1.amazonaws.com",
    "pets": "/Test",
    "port": 443
}


# Utility functions
def get_resolved_value(request, slot_name):
    """Resolve the slot name from the request using resolutions."""
    # type: (IntentRequest, str) -> Union[str, None]
    try:
        return (request.intent.slots[slot_name].resolutions.
                resolutions_per_authority[0].values[0].value.name)
    except (AttributeError, ValueError, KeyError, IndexError, TypeError) as e:
        logger.info("Couldn't resolve {} for request: {}".format(slot_name, request))
        logger.info(str(e))
        return None

def get_slot_values(filled_slots):
    """Return slot values with additional info."""
    # type: (Dict[str, Slot]) -> Dict[str, Any]
    slot_values = {}
    logger.info("Filled slots: {}".format(filled_slots))

    for key, slot_item in six.iteritems(filled_slots):
        name = slot_item.name
        try:
            status_code = slot_item.resolutions.resolutions_per_authority[0].status.code

            if status_code == StatusCode.ER_SUCCESS_MATCH:
                slot_values[name] = {
                    "synonym": slot_item.value,
                    "resolved": slot_item.resolutions.resolutions_per_authority[0].values[0].value.name,
                    "is_validated": True,
                }
            elif status_code == StatusCode.ER_SUCCESS_NO_MATCH:
                slot_values[name] = {
                    "synonym": slot_item.value,
                    "resolved": slot_item.value,
                    "is_validated": False,
                }
            else:
                pass
        except (AttributeError, ValueError, KeyError, IndexError, TypeError) as e:
            logger.info("Couldn't resolve status_code for slot item: {}".format(slot_item))
            logger.info(e)
            slot_values[name] = {
                "synonym": slot_item.value,
                "resolved": slot_item.value,
                "is_validated": False,
            }
    return slot_values

def random_phrase(str_list):
    """Return random element from list."""
    # type: List[str] -> str
    return random.choice(str_list)

def build_book_match_options(host_name, path, port, slot_values):
    """Return options for HTTP Get call."""
    # type: (str, str, int, Dict[str, Any]) -> Dict
    #path_params = {
     #   "SSET": "book-{}-{}".format(
     #       slot_values["genre"]["resolved"],
     #       slot_values["author"]["resolved"]
            
    #}
    #if host_name[:4] != "http":
     #   host_name = "https://{}".format(host_name)
    #url = "{}:{}{}".format(host_name, str(port), path)
    return {
        "genre": slot_values["genre"]["resolved"],
        "author": slot_values["author"]["resolved"]
    }

def http_get(http_options):
    genre = http_options["genre"]
    author = http_options["author"]
    b='none'
    book = {}
    
    if (genre=="Adventure") and (author=="Homer")
		b= "The Odyssey"
	elif (genre=="Adventure") and (author=="Jonathan Swift"):
		b= "Gulliver's Travels"
	else:
	    b="unable to find"
	    
	book['title'] = b

    return json.dumps(book)


# Skill Builder object
sb = SkillBuilder()

# Add all request handlers to the skill.
sb.add_request_handler(LaunchRequestHandler())
#sb.add_request_handler(MythicalCreaturesHandler())
sb.add_request_handler(InProgressBookMatchIntent())
sb.add_request_handler(CompletedBookMatchIntent())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(ExitIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

# Add exception handler to the skill.
sb.add_exception_handler(CatchAllExceptionHandler())

# Add response interceptor to the skill.
sb.add_global_request_interceptor(RequestLogger())
sb.add_global_response_interceptor(ResponseLogger())

# Expose the lambda handler to register in AWS Lambda.
lambda_handler = sb.lambda_handler()
