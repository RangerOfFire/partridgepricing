import json, sys, logging

from pony.orm import Database, Required, Optional, Set, db_session
import requests


logging.basicConfig(level=logging.DEBUG)
db = Database()

class BaseModel(object):
    pass

class Hotel(BaseModel, db.Entity):
    __table__ = "hotel"
    brand = Required(str, default="Travelodge")
    brand_pk = Required(str)  # site_no
    name = Optional(str)
    address = Optional(str)
    address_postcode = Optional(str)
    room_total = Optional(int)
    latitude = Optional(float)
    longitude = Optional(float)
    parking_type_id = Optional(int)


class TravelodgeJSONDecoder(json.JSONDecoder):
    def default(self, obj):
        if isinstance(obj, str) and obj in ('T', 'F'):
            return obj == 'T'
        return super(TravelodgeJSONDecoder, self).default(obj)


def bind_db():
    db.bind("sqlite", "travelodge.db", create_db=True)
    db.generate_mapping(create_tables=True)

@db_session
def get_hotels():
    payload = {
        "searchRequest": {
            "location": "Watford",
            "maxResults": 10,
        }
    }
    response = requests.post("https://www.travelodge.co.uk/travelodgeAPI/search/gethotelsbylocation", json=payload)
    hotels = response.json(cls=TravelodgeJSONDecoder)
    for key, hotel_data in hotels["searchResponse"]["hotels"].iteritems():
        logging.debug("Got %s (%s)" % (key, hotel_data["name"]))
        hotel = Hotel.get(brand_pk=key)
        if hotel is None:
            # CREATE
            hotel = Hotel(brand_pk=key)
        # UPDATE
        hotel.name = hotel_data["name"]
        hotel.address = "%s, %s" % (hotel_data["address1"], hotel_data["address4"])
        hotel.address_postcode = hotel_data["postcode"] or hotel_data["srch_postcode"]
        hotel.room_total = hotel_data["room_total"]
        hotel.latitude = hotel_data["latitude"]
        hotel.longitude = hotel_data["longitude"]
        hotel.parking_type_id = hotel_data["parking_type_id"]

def get_rates_for_hotel(hotel_code):
    payload = {
        "availabilityRequest": {
            "checkInDate": "06-02-2016",
            "noRooms": 1,
            "noNights": 1,
            "userType": "leisure",
            "roomPreference": [  # This is actually occupancy not preference
                {
                    "noAdult": 1,
                    "noChild": 0,
                }
            ],
            "siteCode": [
                hotel_code
            ],
            "includeDisabled": "F",
        }
    }

    response = requests.post("https://www.travelodge.co.uk/travelodgeAPI/availability/gethotelratesbysitecode", json=payload)
    rooms = response.json(cls=TravelodgeJSONDecoder)
    if 'error' in rooms:
        logging.error("Request error: %s" % rooms)
        return
    for key, room_data in rooms["availabilityResponse"]["rooms"].iteritems():
        logging.debug("Saver rate: %s" % room_data["Double Room"]["rates"]["saver"]["totalRate"])

if __name__ == "__main__":
    bind_db()

    cmd = sys.argv[1]
    if cmd in locals():
        logging.debug("Running %s" % cmd)
        locals()[cmd](*sys.argv[2:])

