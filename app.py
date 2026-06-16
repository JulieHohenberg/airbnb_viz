import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(
    page_title="Boston Airbnb Dashboard",
    page_icon="🏙️",
    layout="wide"
)

alt.data_transformers.disable_max_rows()

FILE_ID = "1Q-bnOdbb5753U5FhSqWgCpmo-AsemeFW"
DATA_URL = f"https://drive.google.com/uc?export=download&id={FILE_ID}"
LOCAL_FILE = "listings.csv"

REQUIRED_COLUMNS = [
    "neighbourhood_cleansed",
    "room_type",
    "availability_365",
    "hosts_time_as_user_years",
    "review_scores_cleanliness",
    "review_scores_communication",
    "review_scores_location",
    "review_scores_value",
    "estimated_occupancy_l365d",
    "number_of_reviews",
    "host_is_superhost"
]

REVIEW_COLUMNS = [
    "review_scores_cleanliness",
    "review_scores_communication",
    "review_scores_location",
    "review_scores_value"
]

SCORE_LABELS = {
    "review_scores_cleanliness": "Cleanliness",
    "review_scores_communication": "Communication",
    "review_scores_location": "Location",
    "review_scores_value": "Value"
}

HOST_TENURE_ORDER = [
    "New Host (<2 years)",
    "Established Host (2-5 years)",
    "Veteran Host (5+ years)"
]

SCORE_ORDER = ["Cleanliness", "Communication", "Location", "Value"]


@st.cache_data(show_spinner=False)
def load_data():
    # Load from Google Drive
    try:
        data = pd.read_csv(DATA_URL)
    except Exception:
        data = pd.read_csv(LOCAL_FILE)

    # Keep only rows with core fields
    data = data.dropna(subset=["neighbourhood_cleansed", "room_type"])

    # Clean numeric columns
    numeric_columns = [
        "availability_365",
        "hosts_time_as_user_years",
        "estimated_occupancy_l365d",
        "number_of_reviews"
    ] + REVIEW_COLUMNS

    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    return data


def check_columns(data):
    # Check required fields
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing_columns:
        st.error("Missing required columns: " + ", ".join(missing_columns))
        st.stop()


def apply_sidebar_filters(data):
    # Sidebar filters
    st.sidebar.header("Filters")

    room_types = sorted(data["room_type"].dropna().unique())
    selected_room_types = st.sidebar.multiselect(
        "Room type",
        room_types,
        default=room_types
    )

    neighborhood_mode = st.sidebar.radio(
        "Neighborhoods",
        ["All neighborhoods", "Choose neighborhoods"]
    )

    neighborhoods = sorted(data["neighbourhood_cleansed"].dropna().unique())
    if neighborhood_mode == "Choose neighborhoods":
        selected_neighborhoods = st.sidebar.multiselect(
            "Pick neighborhoods",
            neighborhoods,
            default=neighborhoods[:5]
        )
    else:
        selected_neighborhoods = neighborhoods

    superhost_filter = st.sidebar.selectbox(
        "Host type",
        ["All hosts", "Superhosts only", "Non-superhosts only"]
    )

    min_availability = int(data["availability_365"].min())
    max_availability = int(data["availability_365"].max())
    availability_range = st.sidebar.slider(
        "Availability range",
        min_value=min_availability,
        max_value=max_availability,
        value=(min_availability, max_availability)
    )

    max_reviews = int(data["number_of_reviews"].max())
    min_reviews = st.sidebar.slider(
        "Minimum number of reviews",
        min_value=0,
        max_value=max_reviews,
        value=0
    )

    filtered = data[
        data["room_type"].isin(selected_room_types)
        & data["neighbourhood_cleansed"].isin(selected_neighborhoods)
        & data["availability_365"].between(availability_range[0], availability_range[1])
        & (data["number_of_reviews"] >= min_reviews)
    ].copy()

    if superhost_filter == "Superhosts only":
        filtered = filtered[filtered["host_is_superhost"] == "t"]
    elif superhost_filter == "Non-superhosts only":
        filtered = filtered[filtered["host_is_superhost"] == "f"]

    return filtered


def make_score_tenure_chart(data):
    # Review score chart
    scores = data.dropna(subset=["hosts_time_as_user_years"] + REVIEW_COLUMNS).copy()

    if scores.empty:
        return None

    scores["host_tenure_group"] = pd.cut(
        scores["hosts_time_as_user_years"],
        bins=[float("-inf"), 2, 5, float("inf")],
        labels=HOST_TENURE_ORDER,
        right=False
    )

    scores_long = scores.melt(
        id_vars=["host_tenure_group"],
        value_vars=REVIEW_COLUMNS,
        var_name="score_type",
        value_name="score"
    )

    scores_long["score_type_clean"] = scores_long["score_type"].map(SCORE_LABELS)
    scores_long = scores_long.dropna(subset=["score"])

    grouped_scores = scores_long.groupby(
        ["host_tenure_group", "score_type_clean"],
        observed=False
    ).agg(
        average_score=("score", "mean"),
        listings=("score", "count")
    ).reset_index()

    return alt.Chart(grouped_scores).mark_bar().encode(
        x=alt.X(
            "score_type_clean:N",
            title="Review Score Type",
            sort=SCORE_ORDER,
            axis=alt.Axis(labelAngle=0)
        ),
        xOffset=alt.XOffset(
            "host_tenure_group:N",
            sort=HOST_TENURE_ORDER
        ),
        y=alt.Y(
            "average_score:Q",
            title="Average Review Score",
            scale=alt.Scale(domain=[4.5, 5])
        ),
        color=alt.Color(
            "host_tenure_group:N",
            title="Host Tenure",
            sort=HOST_TENURE_ORDER,
            scale=alt.Scale(
                domain=HOST_TENURE_ORDER,
                range=["#cfe8f3", "#73add1", "#2166ac"]
            ),
            legend=alt.Legend(
                orient="bottom",
                columns=1,
                labelLimit=0,
                titleLimit=0
            )
        ),
        tooltip=[
            alt.Tooltip("score_type_clean:N", title="Score Type"),
            alt.Tooltip("host_tenure_group:N", title="Host Tenure"),
            alt.Tooltip("average_score:Q", title="Average Score", format=".2f"),
            alt.Tooltip("listings:Q", title="Listings")
        ]
    ).properties(
        title="Average Review Scores by Host Tenure",
        width=850,
        height=420
    ).configure_axis(
        labelFontSize=13,
        titleFontSize=15
    ).configure_title(
        fontSize=20
    ).configure_legend(
        labelFontSize=13,
        titleFontSize=15,
        symbolSize=160
    )


def make_room_type_chart(data):
    # Linked neighborhood chart
    neighborhood_select = alt.selection_point(
        fields=["neighbourhood_cleansed"],
        empty="all"
    )

    neighborhood_counts = data.groupby("neighbourhood_cleansed").size().reset_index(name="listings")

    availability_by_room = data.groupby(
        ["neighbourhood_cleansed", "room_type"]
    ).agg(
        average_availability=("availability_365", "mean"),
        listings=("room_type", "count")
    ).reset_index()

    neighborhood_filter = alt.Chart(neighborhood_counts).mark_bar().encode(
        x=alt.X("listings:Q", title="Number of Listings"),
        y=alt.Y(
            "neighbourhood_cleansed:N",
            sort="-x",
            title="Neighborhood"
        ),
        color=alt.condition(
            neighborhood_select,
            alt.value("black"),
            alt.value("lightgray")
        ),
        tooltip=[
            alt.Tooltip("neighbourhood_cleansed:N", title="Neighborhood"),
            alt.Tooltip("listings:Q", title="Listings")
        ]
    ).add_params(
        neighborhood_select
    ).properties(
        title="Select a Neighborhood",
        width=380,
        height=520
    )

    room_type_availability = alt.Chart(availability_by_room).mark_bar().encode(
        x=alt.X("room_type:N", title="Room Type", axis=alt.Axis(labelAngle=0)),
        y=alt.Y(
            "average_availability:Q",
            title="Average Days Available Per Year"
        ),
        color=alt.Color("room_type:N", title="Room Type"),
        tooltip=[
            alt.Tooltip("room_type:N", title="Room Type"),
            alt.Tooltip("average_availability:Q", title="Average Availability", format=".1f"),
            alt.Tooltip("listings:Q", title="Listings")
        ]
    ).transform_filter(
        neighborhood_select
    ).properties(
        title="Average Yearly Availability by Room Type",
        width=520,
        height=380
    )

    return (neighborhood_filter | room_type_availability).configure_axis(
        labelFontSize=12,
        titleFontSize=14
    ).configure_title(
        fontSize=18
    ).configure_legend(
        labelFontSize=12,
        titleFontSize=14
    )


def make_occupancy_chart(data):
    # Brushed occupancy chart
    occupancy = data.groupby("neighbourhood_cleansed").agg(
        total_listings=("neighbourhood_cleansed", "count"),
        occupied_days=("estimated_occupancy_l365d", "sum")
    ).reset_index()

    occupancy["avg_daily_occupied_listings"] = occupancy["occupied_days"] / 365
    occupancy = occupancy.sort_values("total_listings", ascending=False)

    brush = alt.selection_interval(
        encodings=["y"],
        name="neighborhood_brush"
    )

    legend_settings = alt.Legend(
        orient="bottom",
        labelLimit=0,
        titleLimit=0,
        columns=2
    )

    base = alt.Chart(occupancy).encode(
        y=alt.Y(
            "neighbourhood_cleansed:N",
            sort=alt.EncodingSortField(
                field="total_listings",
                order="descending"
            ),
            title="Neighborhood"
        ),
        opacity=alt.condition(
            brush,
            alt.value(1),
            alt.value(0.25)
        ),
        tooltip=[
            alt.Tooltip("neighbourhood_cleansed:N", title="Neighborhood"),
            alt.Tooltip("total_listings:Q", title="Total Listings"),
            alt.Tooltip(
                "avg_daily_occupied_listings:Q",
                title="Estimated Occupied Listings",
                format=".1f"
            )
        ]
    )

    total_bar = base.mark_bar().encode(
        x=alt.X(
            "total_listings:Q",
            title="Number of Listings",
            axis=alt.Axis(labelAngle=-30)
        ),
        color=alt.Color(
            "bar_type:N",
            title="Bar Meaning",
            scale=alt.Scale(
                domain=["Total Listings", "Estimated Occupied Listings"],
                range=["lightgray", "steelblue"]
            ),
            legend=legend_settings
        )
    ).transform_calculate(
        bar_type="'Total Listings'"
    )

    occupied_bar = base.mark_bar().encode(
        x=alt.X(
            "avg_daily_occupied_listings:Q",
            title="Number of Listings",
            axis=alt.Axis(labelAngle=-30)
        ),
        color=alt.Color(
            "bar_type:N",
            title="Bar Meaning",
            scale=alt.Scale(
                domain=["Total Listings", "Estimated Occupied Listings"],
                range=["lightgray", "steelblue"]
            ),
            legend=legend_settings
        )
    ).transform_calculate(
        bar_type="'Estimated Occupied Listings'"
    )

    selected_summary = alt.Chart(occupancy).mark_bar().encode(
        x=alt.X("avg_daily_occupied_listings:Q", title="Estimated Occupied Listings"),
        y=alt.Y(
            "neighbourhood_cleansed:N",
            sort=alt.EncodingSortField(
                field="avg_daily_occupied_listings",
                order="descending"
            ),
            title=None
        ),
        tooltip=[
            alt.Tooltip("neighbourhood_cleansed:N", title="Neighborhood"),
            alt.Tooltip("avg_daily_occupied_listings:Q", title="Estimated Occupied Listings", format=".1f"),
            alt.Tooltip("total_listings:Q", title="Total Listings")
        ]
    ).transform_filter(
        brush
    ).properties(
        title="Brushed Neighborhoods",
        width=320,
        height=600
    )

    overlay = (total_bar + occupied_bar).add_params(
        brush
    ).properties(
        title="Total Listings vs. Estimated Occupied Listings by Neighborhood",
        width=760,
        height=600
    )

    return (overlay | selected_summary).configure_axis(
        labelFontSize=12,
        titleFontSize=14
    ).configure_title(
        fontSize=18
    ).configure_legend(
        labelFontSize=12,
        titleFontSize=14,
        symbolSize=160
    )


def show_metrics(data):
    # Dashboard metrics
    col1, col2, col3, col4 = st.columns(4)

    listings = len(data)
    neighborhoods = data["neighbourhood_cleansed"].nunique()
    average_availability = data["availability_365"].mean()
    average_rating = data["review_scores_value"].mean()

    col1.metric("Listings", f"{listings:,}")
    col2.metric("Neighborhoods", f"{neighborhoods:,}")
    col3.metric("Avg. Availability", f"{average_availability:.0f} days")
    col4.metric("Avg. Value Score", f"{average_rating:.2f}")


def main():
    # App title
    st.title("Boston Airbnb Listings Dashboard")
    st.markdown(
        "This dashboard looks at how Boston Airbnb listings differ by host experience, "
        "room type, availability, and neighborhood activity. The main pattern to watch is "
        "whether the biggest listing markets also have the strongest estimated occupancy."
    )

    data = load_data()
    check_columns(data)
    filtered_data = apply_sidebar_filters(data)

    if filtered_data.empty:
        st.warning("No listings match the current filters.")
        st.stop()

    show_metrics(filtered_data)

    st.divider()
    st.subheader("1. Host experience and review scores")
    st.markdown(
        "Review scores are tightly packed near the top of the scale, so small differences still matter. "
        "This view compares newer, established, and veteran hosts across the main review categories."
    )
    score_chart = make_score_tenure_chart(filtered_data)
    if score_chart is None:
        st.info("Not enough review score data for the selected filters.")
    else:
        st.altair_chart(score_chart, use_container_width=True)

    st.divider()
    st.subheader("2. Availability by room type")
    st.markdown(
        "Click a neighborhood on the left to see how yearly availability changes by room type. "
        "This helps separate places with many listings from places where those listings are often open."
    )
    st.altair_chart(make_room_type_chart(filtered_data), use_container_width=True)

    st.divider()
    st.subheader("3. Listings compared with estimated occupancy")
    st.markdown(
        "The gray bar shows total listings, while the blue bar estimates how many listings are occupied on an average day. "
        "Brush over multiple neighborhoods to compare a focused group on the right."
    )
    st.altair_chart(make_occupancy_chart(filtered_data), use_container_width=True)

    st.caption("Source: Boston Airbnb listings loaded from Google Drive.")


if __name__ == "__main__":
    main()
