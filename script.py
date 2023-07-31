from datetime import date, timedelta
import isodate

import os
from dotenv import load_dotenv
import pandas as pd

from duffel_api import Duffel
from duffel_api.http_client import ApiError


load_dotenv()

DUFFEL_ACCESS_TOKEN = os.getenv("DUFFEL_ACCESS_TOKEN")
client = Duffel(access_token=DUFFEL_ACCESS_TOKEN)

FLIGHTS_PKL_PATH = os.getenv("FLIGHTS_PKL_PATH")


def get_best_flights(origin, destination, depart_date, return_date):
    try:
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
        outbound_offers_list = list(
            filter(lambda x: x.owner.name != "Duffel Airways", outbound_offers_list)
        )
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
            partial_offer_request.id,
            [outbound_partial_offer_id, inbound_partial_offer_id],
        )
        fares_offers_list = fares_offer_request.offers
        fares_offers_list.sort(key=lambda x: float(x.total_amount))

        selected_offer = fares_offers_list[0]
        priced_offer = client.offers.get(
            selected_offer.id, return_available_services=False
        )

        return priced_offer
    except ApiError as exc:
        print(f"Request ID: {exc.meta['request_id']}")
        print(f"Status Code: {exc.meta['status']}")
        print("Errors: ")
        for error in exc.errors:
            print(f" Title: {error['title']}")
            print(f" Code: {error['code']}")
            print(f" Message: {error['message']}")


if __name__ == "__main__":
    # Setup
    try:
        df = pd.read_pickle(FLIGHTS_PKL_PATH)
    except FileNotFoundError:
        df = pd.DataFrame()

    # Get prices
    origin = "WAW"
    destination = "GOT"

    first_date_outbound = date(2023, 10, 2)
    last_date_outbound = date(2023, 10, 14)
    days_diff = (last_date_outbound - first_date_outbound).days

    min_days = 2
    max_days = 5

    for outbound_departure_date in [
        first_date_outbound + timedelta(days=x) for x in range(days_diff + 1)
    ]:
        print(outbound_departure_date, end="", flush=True)

        for trip_days in range(min_days, max_days + 1):
            inbound_departure_date = outbound_departure_date + timedelta(days=trip_days)
            best_offer = get_best_flights(
                origin, destination, outbound_departure_date, inbound_departure_date
            )
            if best_offer is not None:
                (outbound_slice, inbound_slice) = best_offer.slices
                new_flight_df = pd.DataFrame(
                    {
                        "origin": origin,
                        "destination": destination,
                        "outbound_depart": outbound_slice.segments[0].departing_at,
                        "outbound_arrive": outbound_slice.segments[-1].arriving_at,
                        "outbound_duration": sum(
                            list(
                                map(
                                    lambda x: isodate.parse_duration(x.duration),
                                    outbound_slice.segments,
                                )
                            ),
                            timedelta(),
                        ),
                        "inbound_depart": inbound_slice.segments[0].departing_at,
                        "inbound_arrive": inbound_slice.segments[-1].arriving_at,
                        "inbound_duration": sum(
                            list(
                                map(
                                    lambda x: isodate.parse_duration(x.duration),
                                    inbound_slice.segments,
                                )
                            ),
                            timedelta(),
                        ),
                        "total_amount": float(best_offer.total_amount),
                        "airline": best_offer.owner.name,
                        "trip_days": (
                            inbound_slice.segments[-1].arriving_at
                            - outbound_slice.segments[0].departing_at
                        ).days,
                    },
                    index=[best_offer.id],
                )
                df = pd.concat([df, new_flight_df], ignore_index=True)
            print(".", end="", flush=True)

        # Save
        df.to_pickle(FLIGHTS_PKL_PATH)
        print()
    print("\nDone")
