'''
Hackpack Configure
A script to configure your TwiML apps and Twilio phone numbers to use your
hackpack's Heroku app.

Usage:

Auto-configure using your local_settings.py:
    python configure.py

Deploy to new Twilio number and App Sid:
    python configure.py --new

Deploy to specific App Sid:
    python configure.py --app APxxxxxxxxxxxxxx

Deploy to specific Twilio number:
    python configure.py --number +15556667777

Deploy to custom domain:
    python configure.py --domain example.com
'''

from optparse import OptionParser
import sys
import logging

from twilio.rest import TwilioRestClient
from twilio import TwilioRestException

import local_settings


class Configure(object):
    def __init__(self, account_sid=local_settings.TWILIO_ACCOUNT_SID,
            auth_token=local_settings.TWILIO_AUTH_TOKEN,
            app_sid=local_settings.TWILIO_APP_SID,
            phone_number=local_settings.TWILIO_CALLER_ID,
            voice_url='/voice',
            sms_url='/sms',
            host=None):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.app_sid = app_sid
        self.phone_number = phone_number
        self.host = host
        self.voice_url = voice_url
        self.sms_url = sms_url

    def start(self):
        logging.info("Configuring your Twilio hackpack...")
        logging.debug("Checking if credentials are set...")
        if not self.account_sid:
            raise ConfigurationError("ACCOUNT_SID is not set in " \
                    "local_settings.")
        if not self.auth_token:
            raise ConfigurationError("AUTH_TOKEN is not set in " \
                    "local_settings.")

        logging.debug("Creating Twilio client...")
        self.client = TwilioRestClient(self.account_sid, self.auth_token)

        logging.debug("Checking if host is set.")
        if not self.host:
            logging.debug("Hostname is not set...")
            self.host = self.getHerokuHostname()

        # Check if urls are set.
        logging.debug("Checking if all urls are set.")
        if "http://" not in self.voice_url:
            self.voice_url = self.host + self.voice_url
            logging.debug("Setting voice_url with host: %s" % self.voice_url)
        if "http://" not in self.sms_url:
            self.sms_url = self.host + self.sms_url
            logging.debug("Setting sms_url with host: %s" % self.sms_url)

        return self.configureHackpack(self.voice_url, self.sms_url,
                self.app_sid, self.phone_number)

    def configureHackpack(self, voice_url, sms_url, app_sid,
            phone_number, *args):

        # Check if app sid is configured and available.
        if not app_sid:
            app = self.createNewTwiMLApp(voice_url, sms_url)
        else:
            app = self.setAppRequestUrls(app_sid, voice_url, sms_url)

        # Check if phone_number is set.
        if not phone_number:
            number = self.purchasePhoneNumber()
        else:
            number = self.retrievePhoneNumber(phone_number)

        # Configure phone number to use App Sid.
        logging.info("Setting %s to use application sid: %s" %
                (number.friendly_name, app.sid))
        try:
            self.client.phone_numbers.update(number.sid,
                    voice_application_sid=app.sid,
                    sms_application_sid=app.sid,
                    friendly_name="Hackpack for Heroku and Flask")
            logging.debug("Number set.")
        except TwilioRestException, e:
            raise ConfigurationError("An error occurred setting the " \
                    "application sid for %s: %s" % (number.friendly_name,
                        e))

        # We're done!
        if number:
            logging.info("Hackpack is now configured.  Call %s to test!"
                    % number.friendly_name)
            return number
        else:
            raise ConfigurationError("An unknown error occurred configuring " \
                    "request urls for this hackpack.")

    def createNewTwiMLApp(self, voice_url, sms_url):
        logging.debug("Asking user to create new app sid...")
        choice = raw_input("Your APP_SID is not configured in your " \
            "local_settings.  Create a new one? [y/n]").lower()
        while True:
            if choice == "y":
                try:
                    logging.info("Creating new application...")
                    app = self.client.applications.create(voice_url=voice_url,
                            sms_url=sms_url)
                    break
                except TwilioRestException, e:
                    raise ConfigurationError("Your Twilio app couldn't " \
                            "be created: %s" % e)
            elif choice == "n":
                raise ConfigurationError("Your APP_SID setting must be  " \
                        "set in local_settings.")
            else:
                sys.stdout.write("Please choose yes or no with a 'y' or 'n'")
        if app:
            logging.debug("Application created: %s" % app.sid)
            return app
        else:
            raise ConfigurationError("There was an unknown error " \
                    "creating your TwiML application.")

    def setAppRequestUrls(self, app_sid, voice_url, sms_url):
        logging.info("Setting request urls for application sid: %s" \
                % app_sid)

        # If voice_url or sms_url not FQDN, use stored host
        for arg in (voice_url, sms_url):
            if "http://" not in arg and self.host:
                arg = self.host + arg

        try:
            app = self.client.applications.update(app_sid, voice_url=voice_url,
                    sms_url=sms_url,
                    friendly_name="Hackpack for Heroku and Flask")
        except TwilioRestException, e:
            if "404" in e:
                raise ConfigurationError("This application sid was not " \
                        "found: %s" % app_sid)
            else:
                raise ConfigurationError("An error setting the request URLs " \
                        "occured: %s" % e)
        if app:
            logging.debug("Updated application sid: %s " % app.sid)
            return app
        else:
            raise ConfigurationError("An unknown error occuring "\
                   "configuring request URLs for app sid.")

    def retrievePhoneNumber(self, phone_number):
        logging.debug("Retrieving phone number: %s" % phone_number)
        try:
            logging.debug("Getting sid for phone number: %s" % phone_number)
            number = self.client.phone_numbers.list(
                    phone_number=phone_number)
        except TwilioRestException, e:
            raise ConfigurationError("An error setting the request URLs " \
                    "occured: %s" % e)
        if number:
            logging.debug("Retrieved sid: %s" % number[0].sid)
            return number[0]
        else:
            raise ConfigurationError("An unknown error occurred retrieving " \
                    "number: %s" % phone_number)

    def purchasePhoneNumber(self):
        logging.debug("Asking user to purchase phone number...")

        # Find number to purchase
        choice = raw_input("Your CALLER_ID is not configured in your " \
            "local_settings.  Purchase a new one? [y/n]").lower()

        # Confirm phone number purchase.
        choice = raw_input("You are sure you want to purchase? " \
            "Your Twilio account will be charged $1. [y/n]").lower()
        while True:
            if choice == "y":
                try:
                    logging.debug("Purchasing phone number...")
                    number = self.client.phone_numbers.purchase()
                    logging.debug("Phone number purchased: %s" %
                            number.friendly_name)
                    break
                except TwilioRestException, e:
                    raise ConfigurationError("Your Twilio app couldn't " \
                            "be created: %s" % e)
            elif choice == "n":
                raise ConfigurationError("To configure this " \
                        "hackpack CALLER_ID must set in local_settings or " \
                        "a phone number must be purchased.")
            else:
                sys.stdout.write("Please choose yes or no with a 'y' or 'n'")

        # Return number or error out.
        if number:
            logging.debug("Returning phone number: %s " % number.friendly_name)
            return number
        else:
            raise ConfigurationError("There was an unknown error purchasing " \
                    "your phone number.")

    def getHerokuHostname(self, git_config_path='./.git/config'):
        logging.debug("Getting hostname from git configuration file: %s" \
                % git_config_path)
        # Load git configuration
        try:
            logging.debug("Loading git config...")
            git_config = file(git_config_path).readlines()
        except IOError, e:
            raise ConfigurationError("Could not find .git config.  Does it " \
                    "still exist? Failed path: %s" % e)

        logging.debug("Finding Heroku remote in git configuration...")
        subdomain = None
        for line in git_config:
            if "git@heroku.com" in line:
                s = line.split(":")
                subdomain = s[1].replace('.git', '')
                logging.debug("Heroku remote found: %s" % subdomain)

        if subdomain:
            host = "http://%s.herokuapps.com" % subdomain.strip()
            logging.debug("Returning full host: %s" % host)
            return host 
        else:
            raise ConfigurationError("Could not find Heroku remote in " \
                    "your .git config.  Have you created the Heroku app?")


class ConfigurationError(Exception):
    def __init__(self, message):
        #Exception.__init__(self, message)
        logging.error(message)


# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

# Parser configuration
usage = "Twilio Hackpack Configurator - an easy way to configure " \
        "configure your hackpack!\n%prog [options] arg1 arg2"
parser = OptionParser(usage=usage)
parser.add_option("-n", "--new", default=False, action="store_true",
        help="Purchase new Twilio phone number and configure app to use " \
            "your hackpack.")
parser.add_option("-N", "--new_app", default=False, action="store_true",
        help="Create a new TwiML application sid to use for your " \
            "hackpack.")
parser.add_option("-a", "--app_sid", default=None,
        help="Configure specific AppSid to use your hackpack.")
parser.add_option("-#", "--phone_number", default=None,
        help="Configure specific Twilio number to use your hackpack.")
parser.add_option("-v", "--voice_url", default=None,
        help="Set the route for your Voice Request URL: (e.g. '/voice').")
parser.add_option("-s", "--sms_url", default=None,
        help="Set the route for your SMS Request URL: (e.g. '/sms').")
parser.add_option("-d", "--domain", default=None,
        help="Set a custom domain.")
parser.add_option("-D", "--debug", default=False,
        action="store_true", help="Turn on debug output.")


def main():
    (options, args) = parser.parse_args()

    # Configurator configuration :)
    configure = Configure()

    # Options tree
    if options.new:
        configure.phone_number = None
    if options.app_sid:
        configure.app_sid = options.app_sid
    if options.phone_number:
        configure.phone_number = options.phone_number
    if options.voice_url:
        configure.voice_url = options.voice_url
    if options.sms_url:
        configure.sms_url = options.sms_url
    if options.domain:
        configure.host = options.domain
    if options.debug:
        logging.DEBUG

    configure.start()

if __name__ == "__main__":
    main()
