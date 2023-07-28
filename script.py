from datetime import date, timedelta
import isodate
from duffel_api import Duffel

import os
from dotenv import load_dotenv
from pathlib import Path

dotenv_path = Path('.env')
load_dotenv(dotenv_path=dotenv_path)

DUFFEL_ACCESS_TOKEN = os.getenv('DUFFEL_ACCESS_TOKEN')
client = Duffel(access_token=DUFFEL_ACCESS_TOKEN)

origin = "PER"
destination = "KRK"

def get_best_flights(origin, destination, depart_date, return_date):
    slices = [
        {
            "origin": origin,
            "destination": destination,
            "departure_date": depart_date.strftime("%Y-%m-%d"),
        },
        {
            "origin": destination,
            "destination": origin,
            "departure_date": return_date.strftime("%Y-%m-%d"),
        },
    ]

    partial_offer_request = (
        client.partial_offer_requests.create()
        .passengers([{"type": "adult"}])
        .slices(slices)
        .execute()
    )

    outbound_offers_list = partial_offer_request.offers
    outbound_offers_list = list(filter(lambda x: x.owner.name != "Duffel Airways", outbound_offers_list))
    if len(outbound_offers_list) == 0:
        return None

    outbound_offers_list.sort(key=lambda x: float(x.total_amount))

    outbound_lowest_offer = outbound_offers_list[0]
    outbound_partial_offer_id = outbound_lowest_offer.id

    inbound_offer_request = client.partial_offer_requests.get(
        partial_offer_request.id, outbound_partial_offer_id
    )

    inbound_offers_list = inbound_offer_request.offers
    inbound_offers_list.sort(key=lambda x: float(x.total_amount))

    inbound_lowest_offer = inbound_offers_list[0]
    inbound_partial_offer_id = inbound_lowest_offer.id

    fares_offer_request = client.partial_offer_requests.fares(
        partial_offer_request.id, [outbound_partial_offer_id, inbound_partial_offer_id]
    )
    fares_offers_list = fares_offer_request.offers
    fares_offers_list.sort(key=lambda x: float(x.total_amount))

    selected_offer = fares_offers_list[0]
    priced_offer = client.offers.get(selected_offer.id, return_available_services=False)

    return priced_offer

if __name__ == "__main__":
    first_date_outbound = date(2023, 10, 9)
    last_date_outbound = date(2023, 10, 10)
    days_diff = (last_date_outbound - first_date_outbound).days

    min_days = 13
    max_days = 15
    
    best_offers = []
    for outbound_departure_date in [first_date_outbound + timedelta(days=x) for x in range(days_diff+1)]:
        for trip_days in range(min_days, max_days+1):
            inbound_departure_date = outbound_departure_date + timedelta(days=trip_days)
            best_offer = get_best_flights(origin, destination, outbound_departure_date, inbound_departure_date)
            if best_offer is not None:
                best_offers.append((outbound_departure_date, trip_days, best_offer))
            print(".", end="", flush=True)
    print()

    best_offers.sort(key=lambda x: float(x[2].total_amount))

    for (departure_date, trip_days, offer) in best_offers:
        print(f"{departure_date} ({trip_days}): {offer.owner.name}: {offer.total_amount} {offer.total_currency}")
        slices = offer.slices
        outbound_slice = slices[0]
        outbound_departing_at = outbound_slice.segments[0].departing_at
        outbound_arriving_at = outbound_slice.segments[-1].arriving_at
        outbound_segments = len(outbound_slice.segments)
        outbound_duration = sum(list(map(lambda x: isodate.parse_duration(x.duration), outbound_slice.segments)), timedelta())
        
        inbound_slice = slices[1]
        inbound_departing_at = inbound_slice.segments[0].departing_at
        inbound_arriving_at = inbound_slice.segments[-1].arriving_at
        inbound_segments = len(inbound_slice.segments)
        inbound_duration = sum(list(map(lambda x: isodate.parse_duration(x.duration), inbound_slice.segments)), timedelta())

        duration = sum(list(map(lambda x: isodate.parse_duration(x.duration), slices)), timedelta())
        print(f"\t Out: ({outbound_segments}: {outbound_duration}) {outbound_departing_at} -> {outbound_arriving_at}")
        print(f"\t In:  ({inbound_segments}: {inbound_duration}) {inbound_departing_at} -> {inbound_arriving_at}")