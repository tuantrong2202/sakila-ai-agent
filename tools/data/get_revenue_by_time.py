from db import get_connection


ALLOWED_GROUPS = {
    "day",
    "month",
    "quarter",
    "year",
    "category",
}


def get_revenue_by_time(
    start_date=None,
    end_date=None,
    group_by="month",
    category=None,
):
    """
    Calculate revenue over a selected time range.

    Revenue is based on payment.amount and payment.payment_date.

    Parameters:
        start_date: YYYY-MM-DD, inclusive
        end_date: YYYY-MM-DD, inclusive
        group_by: day | month | quarter | year | category
        category: optional category name filter

    Returns:
        Dictionary containing total revenue, transaction count,
        grouped revenue, highest group and lowest group.
    """

    if group_by not in ALLOWED_GROUPS:
        raise ValueError(
            f"Invalid group_by '{group_by}'. "
            f"Allowed values: {sorted(ALLOWED_GROUPS)}"
        )

    conn = get_connection()

    group_expressions = {
        "day": "DATE(p.payment_date)",
        "month": "DATE_FORMAT(p.payment_date, '%Y-%m')",
        "quarter": (
            "CONCAT("
            "YEAR(p.payment_date), "
            "'-Q', "
            "QUARTER(p.payment_date)"
            ")"
        ),
        "year": "YEAR(p.payment_date)",
        "category": "c.name",
    }

    group_expression = group_expressions[group_by]

    query = f"""
        SELECT
            {group_expression} AS group_name,
            COUNT(p.payment_id) AS transaction_count,
            COALESCE(SUM(p.amount), 0) AS revenue
        FROM payment p
        LEFT JOIN rental r
            ON p.rental_id = r.rental_id
        LEFT JOIN inventory i
            ON r.inventory_id = i.inventory_id
        LEFT JOIN film f
            ON i.film_id = f.film_id
        LEFT JOIN film_category fc
            ON f.film_id = fc.film_id
        LEFT JOIN category c
            ON fc.category_id = c.category_id
        WHERE 1 = 1
    """

    params = []

    if start_date:
        query += """
            AND p.payment_date >= %s
        """
        params.append(start_date)

    if end_date:
        query += """
            AND p.payment_date < DATE_ADD(%s, INTERVAL 1 DAY)
        """
        params.append(end_date)

    if category:
        query += """
            AND c.name = %s
        """
        params.append(category)

    query += f"""
        GROUP BY {group_expression}
        ORDER BY {group_expression}
    """

    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        grouped = []

        for row in rows:
            grouped.append(
                {
                    "group": str(row["group_name"]),
                    "transaction_count": int(row["transaction_count"]),
                    "revenue": round(float(row["revenue"]), 2),
                }
            )

        total_revenue = round(
            sum(row["revenue"] for row in grouped),
            2,
        )

        total_transactions = sum(
            row["transaction_count"]
            for row in grouped
        )

        for row in grouped:
            if total_revenue > 0:
                row["revenue_share_pct"] = round(
                    row["revenue"] / total_revenue * 100,
                    2,
                )
            else:
                row["revenue_share_pct"] = 0.0

        highest_group = (
            max(grouped, key=lambda x: x["revenue"])
            if grouped
            else None
        )

        lowest_group = (
            min(grouped, key=lambda x: x["revenue"])
            if grouped
            else None
        )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "group_by": group_by,
            "category_filter": category,
            "total_revenue": total_revenue,
            "total_transactions": total_transactions,
            "grouped_revenue": grouped,
            "highest_revenue_group": highest_group,
            "lowest_revenue_group": lowest_group,
            "data_source": "Sakila MySQL database",
            "revenue_definition": "SUM(payment.amount)",
            "time_definition": "payment.payment_date",
        }

    finally:
        conn.close()
