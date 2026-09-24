from db import get_connection


def get_rental_metrics_by_time(
    start_date=None,
    end_date=None,
    group_by="month",
    category=None,
    store_id=None,
):
    """
    Calculate rental and late-return metrics over time.

    Time basis:
        rental.rental_date

    Population:
        completed rentals only (return_date IS NOT NULL)

    Metrics:
        - rental_count
        - late_rentals
        - on_time_rentals
        - late_rate_pct
        - avg_rental_duration
        - avg_actual_rental_days
        - avg_late_days
    """

    allowed_group_by = {
        "day": "DATE(r.rental_date)",
        "month": "DATE_FORMAT(r.rental_date, '%Y-%m')",
        "quarter": (
            "CONCAT("
            "YEAR(r.rental_date), '-Q', "
            "QUARTER(r.rental_date)"
            ")"
        ),
        "year": "YEAR(r.rental_date)",
    }

    if group_by not in allowed_group_by:
        raise ValueError(
            "group_by must be one of: day, month, quarter, year"
        )

    conn = get_connection()

    try:
        cursor = conn.cursor(dictionary=True)

        where_conditions = [
            "r.return_date IS NOT NULL"
        ]

        params = []

        if start_date:
            where_conditions.append(
                "r.rental_date >= %s"
            )
            params.append(start_date)

        if end_date:
            where_conditions.append(
                "r.rental_date < DATE_ADD(%s, INTERVAL 1 DAY)"
            )
            params.append(end_date)

        if category:
            where_conditions.append(
                "c.name = %s"
            )
            params.append(category)

        if store_id is not None:
            where_conditions.append(
                "i.store_id = %s"
            )
            params.append(store_id)

        group_expr = allowed_group_by[group_by]

        query = f"""
            SELECT
                {group_expr} AS period,

                COUNT(r.rental_id) AS rental_count,

                SUM(
                    CASE
                        WHEN TIMESTAMPDIFF(
                            SECOND,
                            r.rental_date,
                            r.return_date
                        ) / 86400.0 > f.rental_duration
                        THEN 1
                        ELSE 0
                    END
                ) AS late_rentals,

                SUM(
                    CASE
                        WHEN TIMESTAMPDIFF(
                            SECOND,
                            r.rental_date,
                            r.return_date
                        ) / 86400.0 <= f.rental_duration
                        THEN 1
                        ELSE 0
                    END
                ) AS on_time_rentals,

                ROUND(
                    100.0 *
                    SUM(
                        CASE
                            WHEN TIMESTAMPDIFF(
                                SECOND,
                                r.rental_date,
                                r.return_date
                            ) / 86400.0 > f.rental_duration
                            THEN 1
                            ELSE 0
                        END
                    )
                    / COUNT(r.rental_id),
                    2
                ) AS late_rate_pct,

                ROUND(
                    AVG(f.rental_duration),
                    2
                ) AS avg_rental_duration,

                ROUND(
                    AVG(
                        TIMESTAMPDIFF(
                            SECOND,
                            r.rental_date,
                            r.return_date
                        ) / 86400.0
                    ),
                    2
                ) AS avg_actual_rental_days,

                ROUND(
                    AVG(
                        GREATEST(
                            (
                                TIMESTAMPDIFF(
                                    SECOND,
                                    r.rental_date,
                                    r.return_date
                                ) / 86400.0
                            ) - f.rental_duration,
                            0
                        )
                    ),
                    2
                ) AS avg_late_days

            FROM rental r

            JOIN inventory i
                ON r.inventory_id = i.inventory_id

            JOIN film f
                ON i.film_id = f.film_id

            JOIN film_category fc
                ON f.film_id = fc.film_id

            JOIN category c
                ON fc.category_id = c.category_id

            WHERE {" AND ".join(where_conditions)}

            GROUP BY
                {group_expr}

            ORDER BY
                period
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()

        results = []

        for row in rows:
            results.append(
                {
                    "period": str(row["period"]),
                    "rental_count": int(
                        row["rental_count"] or 0
                    ),
                    "late_rentals": int(
                        row["late_rentals"] or 0
                    ),
                    "on_time_rentals": int(
                        row["on_time_rentals"] or 0
                    ),
                    "late_rate_pct": float(
                        row["late_rate_pct"] or 0
                    ),
                    "avg_rental_duration": float(
                        row["avg_rental_duration"] or 0
                    ),
                    "avg_actual_rental_days": float(
                        row["avg_actual_rental_days"] or 0
                    ),
                    "avg_late_days": float(
                        row["avg_late_days"] or 0
                    ),
                }
            )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "group_by": group_by,
            "category": category,
            "store_id": store_id,
            "results": results,
        }

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    result = get_rental_metrics_by_time(
        start_date="2005-05-01",
        end_date="2005-07-31",
        group_by="month",
    )

    print("=" * 70)
    print("RENTAL METRICS BY TIME")
    print("=" * 70)

    for row in result["results"]:
        print(row)
