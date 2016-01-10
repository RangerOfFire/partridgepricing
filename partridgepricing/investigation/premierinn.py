import json, sys, logging

from pony.orm import Database, Required, Optional, Set, db_session
import requests

"""
Deep link:
http://www.premierinn.com/gb/en/hotels/<hotel_details["hotelDetailsPage"]>.html
?INNID=<hotel_details["code"]>&ARRdd=01&ARRmm=02&ARRyyyy=2016&ROOMS=1&NIGHTS=1&ADULT1=1&CHILD1=0&COT1=0&INTTYP1=DB&SID=4&ISH=true&BRAND=PI
"""

logging.basicConfig(level=logging.DEBUG)
db = Database()

class BaseModel(object):
    pass

class Hotel(BaseModel, db.Entity):
    __table__ = "hotel"
    brand = Required(str, default="Premier Inn")
    brand_pk = Required(str)  # code
    name = Optional(str)
    address = Optional(str)
    address_postcode = Optional(str)
    room_total = Optional(int)
    latitude = Optional(float)
    longitude = Optional(float)
    parking_type_id = Optional(int)



def bind_db():
    db.bind("sqlite", "premierinn.db", create_db=True)
    db.generate_mapping(create_tables=True)

@db_session
def get_hotels():
    # Step 1: Get the hotels list
    # GET search/<latitude>/<longitude>/<max_results>
    response = requests.get("http://www.premierinn.com/whitbread-services-unsecured/hotels/search/51.65605/-0.38875/30")
    hotels = response.json()
    hotel_codes = [hotel["code"] for hotel in hotels["hotels"]]

    # Step 2: Get the data for each hotel
    # GET hoteldirectory/<code[0]>/<code>.web.data
    for hotel_code in hotel_codes:
        response = requests.get("http://www.premierinn.com/gb/en/hoteldirectory/%s/%s.web.data" % (hotel_code[0], hotel_code))
        hotel_data = response.json()

        hotel = Hotel.get(brand_pk=hotel_code)
        if hotel is None:
            # CREATE
            hotel = Hotel(brand_pk=hotel_code)

        # UPDATE
        free_parking = any([facility["code"] == "CPF" for facility in hotel_data["facilities"]])
        paid_parking = any([facility["code"] == "CPP" for facility in hotel_data["facilities"]])

        hotel.name = hotel_data["name"]
        hotel.address = "%s, %s" % (hotel_data["address"]["addressline1"], hotel_data["address"]["addressline2"])
        hotel.address_postcode = hotel_data["address"]["postcode"]
        hotel.room_total = 0
        hotel.latitude = hotel_data["map"]["latitude"]
        hotel.longitude = hotel_data["map"]["longitude"]
        hotel.parking_type_id = int(free_parking) + int(paid_parking) * 2


def get_rates_for_hotel(hotel_code):
    payload = {
        "hotelCode": hotel_code,
        "rooms": [
            {
                "type": "DB",
                "adults": 1,
                "children": 0,
                "cotRequired": False,
            }
        ],
        "arrival": "2016-02-01",
        "departure": "2016-02-02",
        "cellCodes": [],
    }

    response = requests.post("http://www.premierinn.com/whitbread-services-unsecured/booking/availability", json=payload)
    availability = response.json()

    if response.status_code != 200:
        logging.error("Request error: %s" % availability)
        return

    if availability["hotelCode"] == hotel_code and availability["available"] and not availability["limitedAvailability"]:
        logging.debug([rate_plan["totalCost"]["amount"] for rate_plan in availability["ratePlans"] if rate_plan["description"] == "Premier Saver"][0])


def get_rates_for_hotels(hotel_codes):
    # Use http://www.premierinn.com/whitbread-services-unsecured/booking/availabilities
    pass


if __name__ == "__main__":
    bind_db()

    cmd = sys.argv[1]
    if cmd in locals():
        logging.debug("Running %s" % cmd)
        locals()[cmd](*sys.argv[2:])

