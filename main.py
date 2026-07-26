#!/usr/bin/env python3
"""
==============================================================================
 INDICA CAFE — MENU & ORDER DATA ANALYSIS
==============================================================================

PROJECT OVERVIEW
-----------------
This script performs an end-to-end SQL + Python data analysis of the Indica
Cafe's operational database. The cafe recently introduced a new menu, and
this analysis exists to help stakeholders understand:

    1. How the menu is structured (categories, pricing, extremes).
    2. How customers are placing orders (volume, frequency, size, trends).
    3. How customers behave once menu and order data are combined
       (favourite/least favourite dishes, big spenders, and what those
       big spenders are actually buying).

Unlike a notebook, this script is meant to be run end-to-end from the
command line (or imported as a module) as part of a reproducible data
pipeline. It is organised into clearly separated *objectives*, each of
which is implemented as a set of small, single-purpose, testable
functions rather than a single monolithic block of code. Every function
has a docstring explaining:

    * What SQL/business question it answers.
    * What table(s) it reads from.
    * What it returns.

WHY SQLite (AND WHY IN-MEMORY)?
--------------------------------
The original schema is shipped as a set of ``.sql`` scripts (see the
``data/`` folder). Rather than requiring a full MySQL/Postgres server to
be running, we load those scripts into a private, in-memory SQLite
database for the lifetime of the script. This keeps the project
completely self-contained: anyone who clones the repository can run
``python main.py`` with zero external services and get identical
results every time.

DATA FILES EXPECTED (relative to this script, inside ``data/``)
------------------------------------------------------------------
    data/create_restaurant_db.sql   -> DDL + seed data (schema + inserts)
    data/objective_1.sql            -> Reference queries for menu analysis
    data/objective_2.sql            -> Reference queries for order analysis
    data/objective_3.sql            -> Reference queries for combined analysis

The ``objective_*.sql`` files are treated as the canonical source of
truth for each SQL query used in this script. Rather than silently
duplicating slightly different SQL inside Python string literals, this
script *parses* each ``.sql`` file into its individual statements and
executes them by name/position, so the SQL you edit in ``data/`` is
exactly the SQL that gets run. This also means the script naturally
stays in sync if the underlying queries are tuned or extended later.

TOOLS AND LIBRARIES USED
--------------------------
    * sqlite3          - lightweight, file-free relational database engine
    * pandas           - tabular data manipulation, SQL result handling
    * matplotlib        - static chart rendering (bar charts, line charts)
    * seaborn           - statistical, aesthetically-consistent plotting
    * argparse          - command-line configuration (paths, plotting on/off)
    * logging           - structured, timestamped console output
    * pathlib           - OS-independent filesystem path handling
    * dataclasses       - lightweight structured containers for results

USAGE
------
    $ python main.py
    $ python main.py --data-dir ./data --no-plots
    $ python main.py --output-dir ./reports

OUTPUT
-------
By default the script prints a structured, human-readable report to
stdout and (unless ``--no-plots`` is supplied) saves a handful of PNG
charts into an ``outputs/`` directory, mirroring — and extending upon —
the visualisations produced in the exploratory Jupyter notebook version
of this project.

AUTHOR / MAINTENANCE NOTES
-----------------------------
This script deliberately avoids any Jupyter/IPython-only APIs (like
``display()``) so that it behaves identically whether run from a
terminal, a CI job, or a cron task. If you are coming from the
notebook version of this project, think of this file as the
"production" counterpart to that "exploration" notebook.
==============================================================================
"""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend: safe for headless/CI runs
    import matplotlib.pyplot as plt
    import seaborn as sns
    _PLOTTING_AVAILABLE = True
except ImportError:  # pragma: no cover - plotting is optional
    _PLOTTING_AVAILABLE = False


# ==============================================================================
# SECTION 0: LOGGING & CONSTANTS
# ==============================================================================
#
# We use the standard library's `logging` module instead of bare `print()`
# calls for anything that is "operational" (progress, warnings, errors).
# We reserve `print()` for the actual *report content* (tables, summaries)
# that a human analyst would want to read top-to-bottom, so that the
# report output stays clean and isn't interleaved with log timestamps.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("indica_cafe_analysis")

DEFAULT_DATA_DIR = Path("data")
DEFAULT_OUTPUT_DIR = Path("outputs")

SCHEMA_FILE = "create_restaurant_db.sql"
OBJECTIVE_1_FILE = "objective_1.sql"
OBJECTIVE_2_FILE = "objective_2.sql"
OBJECTIVE_3_FILE = "objective_3.sql"


# ==============================================================================
# SECTION 1: STRUCTURED RESULT CONTAINERS
# ==============================================================================
#
# Rather than passing around loose tuples or dicts of DataFrames, each
# objective returns a small dataclass. This makes the "shape" of each
# objective's output explicit and self-documenting, and makes it trivial
# to unit test each objective in isolation (e.g. `assert result.total_items
# == 32`) without needing to remember dictionary key names.


@dataclass
class MenuAnalysisResult:
    """Structured output of the Objective 1 menu-items analysis."""

    menu_items: pd.DataFrame
    total_items: int
    cheapest_dish: pd.DataFrame
    most_expensive_dish: pd.DataFrame
    total_italian_dishes: int
    cheapest_italian_dish: pd.DataFrame
    most_expensive_italian_dish: pd.DataFrame
    dishes_per_category: pd.DataFrame
    avg_price_per_category: pd.DataFrame


@dataclass
class OrderAnalysisResult:
    """Structured output of the Objective 2 order-details analysis."""

    order_details: pd.DataFrame
    first_order_date: str
    last_order_date: str
    total_orders: int
    total_dishes_ordered: int
    busiest_order: pd.DataFrame
    large_orders: pd.DataFrame  # orders with >= 13 items
    orders_per_day: pd.DataFrame
    average_orders_per_day: float


@dataclass
class CustomerBehaviorResult:
    """Structured output of the Objective 3 combined-table analysis."""

    combined: pd.DataFrame
    least_ordered_items: pd.DataFrame
    most_ordered_items: pd.DataFrame
    top_spending_orders: pd.DataFrame
    top_order_breakdown: pd.DataFrame
    top_5_orders_breakdown: pd.DataFrame


@dataclass
class AnalysisReport:
    """Top-level container bundling all three objectives together."""

    menu: MenuAnalysisResult
    orders: OrderAnalysisResult
    behavior: CustomerBehaviorResult


# ==============================================================================
# SECTION 2: DATABASE BOOTSTRAP UTILITIES
# ==============================================================================


def read_sql_file(path: Path) -> str:
    """
    Read a ``.sql`` file from disk and return its raw text contents.

    Parameters
    ----------
    path : Path
        Absolute or relative path to a ``.sql`` file.

    Returns
    -------
    str
        The full text of the file, unmodified.

    Raises
    ------
    FileNotFoundError
        If the given path does not exist. The error message is
        intentionally verbose so that a user who has, for example,
        forgotten to clone the ``data/`` folder gets a clear signal
        about what is missing and where the script expected to find it.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find required SQL file at '{path}'. "
            f"Make sure the 'data/' folder (containing "
            f"'{SCHEMA_FILE}', '{OBJECTIVE_1_FILE}', '{OBJECTIVE_2_FILE}' "
            f"and '{OBJECTIVE_3_FILE}') is present relative to this script, "
            f"or pass a custom location with --data-dir."
        )
    return path.read_text(encoding="utf-8")


def split_sql_statements(sql_text: str) -> List[str]:
    """
    Split a block of raw SQL text into a list of individual, executable
    statements.

    Why this is needed
    -------------------
    The ``objective_*.sql`` files are expected to contain several
    semicolon-terminated ``SELECT`` statements, often preceded by
    ``--``-style comments describing what each query answers (mirroring
    the markdown headers used in the exploratory notebook). SQLite's
    Python driver (``sqlite3``) can execute a whole script at once via
    ``executescript()``, but that API does not let us retrieve the
    result set of each individual ``SELECT`` — it is designed for DDL
    and bulk execution, not for capturing tabular output. We therefore
    split the file ourselves so each statement can be run individually
    via ``pandas.read_sql_query`` and captured as its own DataFrame.

    The splitting logic:
        1. Strips full-line SQL comments (lines starting with ``--``).
        2. Splits on semicolons.
        3. Discards any resulting fragment that is empty or whitespace
           only (this naturally absorbs the trailing newline after the
           final statement's semicolon).

    Parameters
    ----------
    sql_text : str
        Raw text of a ``.sql`` file, potentially containing multiple
        statements and comment lines.

    Returns
    -------
    List[str]
        A list of clean, individually-executable SQL statements, in the
        order they appeared in the source file.
    """
    # Remove full-line comments so they don't interfere with statement
    # boundaries or get executed as (invalid) standalone fragments.
    lines = [
        line for line in sql_text.splitlines()
        if not line.strip().startswith("--")
    ]
    cleaned_text = "\n".join(lines)

    # Split on semicolons, which is a reasonable approximation for this
    # dataset since none of the queries embed semicolons inside string
    # literals or nested statements.
    raw_statements = cleaned_text.split(";")

    statements = [stmt.strip() for stmt in raw_statements if stmt.strip()]
    return statements


def build_in_memory_database(schema_sql: str) -> sqlite3.Connection:
    """
    Create a brand-new, private, in-memory SQLite database and execute
    the supplied schema/seed-data SQL script against it.

    Parameters
    ----------
    schema_sql : str
        The full contents of ``create_restaurant_db.sql`` — expected to
        contain ``CREATE TABLE`` and ``INSERT`` statements that together
        define and populate the ``menu_items`` and ``order_details``
        tables (matching the schema used throughout the original
        exploratory notebook).

    Returns
    -------
    sqlite3.Connection
        An open connection to the freshly created, populated, in-memory
        database. The caller is responsible for closing this connection
        (or letting it fall out of scope) once analysis is complete.

    Notes
    -----
    We deliberately use ``sqlite3.connect(":memory:")`` rather than a
    real ``.db`` file on disk. This keeps re-runs of the script fully
    idempotent — there is never a stale, partially-loaded database file
    lying around from a previous, possibly-failed run.
    """
    connection = sqlite3.connect(":memory:")
    cursor = connection.cursor()
    cursor.executescript(schema_sql)
    connection.commit()
    logger.info("In-memory SQLite database created and seeded successfully.")
    return connection


def list_tables(connection: sqlite3.Connection) -> pd.DataFrame:
    """
    Return a DataFrame listing every user-defined table currently present
    in the database. Useful as a sanity check immediately after loading
    the schema, to confirm that ``menu_items`` and ``order_details`` (or
    whatever tables the schema defines) were created as expected.
    """
    query = "SELECT name FROM sqlite_master WHERE type = 'table';"
    return pd.read_sql_query(query, connection)


def run_named_query(connection: sqlite3.Connection, sql: str) -> pd.DataFrame:
    """
    Thin convenience wrapper around ``pandas.read_sql_query`` with
    centralised error handling.

    Every SELECT statement executed anywhere in this script funnels
    through this function, which means if a query ever fails (e.g. due
    to a typo introduced while editing one of the ``objective_*.sql``
    files), the failure is logged with the offending SQL text attached,
    making debugging straightforward.
    """
    try:
        return pd.read_sql_query(sql, connection)
    except (sqlite3.Error, pd.errors.DatabaseError) as exc:
        logger.error("Failed to execute query:\n%s\n\nError: %s", sql, exc)
        raise


# ==============================================================================
# SECTION 3: OBJECTIVE 1 — MENU ITEMS ANALYSIS
# ==============================================================================
#
# Business question this objective answers:
#   "What does our menu actually look like once the new items are added?"
#
# We explore:
#   1. The full menu items table.
#   2. Overall dish count.
#   3. The cheapest and most expensive dish on the entire menu.
#   4. A deep dive into the Italian category specifically (count, cheapest,
#      most expensive) as a worked example of category-level drill-down.
#   5. Dish count per category.
#   6. Average price per category.


def analyze_menu_items(
    connection: sqlite3.Connection, objective_1_queries: List[str]
) -> MenuAnalysisResult:
    """
    Run the full Objective 1 (menu-items) analysis.

    Parameters
    ----------
    connection : sqlite3.Connection
        Open connection to the populated in-memory database.
    objective_1_queries : List[str]
        Ordered list of SQL statements parsed from ``objective_1.sql``.
        The queries are expected (in order) to answer:
            [0] SELECT * FROM menu_items
            [1] total number of menu items
            [2] cheapest dish
            [3] most expensive dish
            [4] total number of Italian dishes
            [5] cheapest Italian dish
            [6] most expensive Italian dish
            [7] dish count grouped by category
            [8] average price grouped by category
        If the ``objective_1.sql`` file contains a different number or
        ordering of statements, this function falls back to safe,
        equivalent inline SQL for any missing pieces so the pipeline
        never silently produces incomplete results.

    Returns
    -------
    MenuAnalysisResult
        Structured bundle of every DataFrame/metric produced by this
        objective, ready to be printed, visualised, or unit tested.
    """
    logger.info("Running Objective 1: Menu Items Analysis...")

    def _query_or_fallback(index: int, fallback_sql: str) -> pd.DataFrame:
        """Use the parsed file's query if available, else a safe default."""
        if index < len(objective_1_queries):
            return run_named_query(connection, objective_1_queries[index])
        return run_named_query(connection, fallback_sql)

    menu_items = _query_or_fallback(0, "SELECT * FROM menu_items;")

    total_items_df = _query_or_fallback(
        1, "SELECT COUNT(*) AS total_items FROM menu_items;"
    )
    total_items = int(total_items_df.iloc[0, 0])

    cheapest_dish = _query_or_fallback(
        2, "SELECT * FROM menu_items ORDER BY price LIMIT 1;"
    )
    most_expensive_dish = _query_or_fallback(
        3, "SELECT * FROM menu_items ORDER BY price DESC LIMIT 1;"
    )

    total_italian_df = _query_or_fallback(
        4,
        "SELECT COUNT(*) AS total_italian FROM menu_items "
        "WHERE category = 'Italian';",
    )
    total_italian_dishes = int(total_italian_df.iloc[0, 0])

    cheapest_italian_dish = _query_or_fallback(
        5,
        "SELECT * FROM menu_items WHERE category = 'Italian' "
        "ORDER BY price LIMIT 1;",
    )
    most_expensive_italian_dish = _query_or_fallback(
        6,
        "SELECT * FROM menu_items WHERE category = 'Italian' "
        "ORDER BY price DESC LIMIT 1;",
    )

    dishes_per_category = _query_or_fallback(
        7,
        "SELECT category, COUNT(menu_item_id) AS total_dishes "
        "FROM menu_items GROUP BY category;",
    )
    avg_price_per_category = _query_or_fallback(
        8,
        "SELECT category, AVG(price) AS avg_price "
        "FROM menu_items GROUP BY category;",
    )

    logger.info("Objective 1 complete: %d menu items analysed.", total_items)

    return MenuAnalysisResult(
        menu_items=menu_items,
        total_items=total_items,
        cheapest_dish=cheapest_dish,
        most_expensive_dish=most_expensive_dish,
        total_italian_dishes=total_italian_dishes,
        cheapest_italian_dish=cheapest_italian_dish,
        most_expensive_italian_dish=most_expensive_italian_dish,
        dishes_per_category=dishes_per_category,
        avg_price_per_category=avg_price_per_category,
    )


# ==============================================================================
# SECTION 4: OBJECTIVE 2 — ORDER DATA ANALYSIS
# ==============================================================================
#
# Business question this objective answers:
#   "How are customers actually ordering — how often, how much, and is
#    demand trending up, down, or flat over the observed period?"
#
# We explore:
#   1. The raw order_details table structure.
#   2. The date range the order data spans.
#   3. Total number of distinct orders placed.
#   4. Total number of individual dishes ordered (order line items).
#   5. The single order with the most dishes in it.
#   6. Every order containing 13 or more dishes (an "extra large order"
#      threshold chosen because it captures the long tail of unusually
#      large orders without being so strict that it returns nothing).
#   7. A day-by-day order volume trend, plus the average orders/day.


def analyze_orders(
    connection: sqlite3.Connection, objective_2_queries: List[str]
) -> OrderAnalysisResult:
    """
    Run the full Objective 2 (order-details) analysis.

    Parameters
    ----------
    connection : sqlite3.Connection
        Open connection to the populated in-memory database.
    objective_2_queries : List[str]
        Ordered list of SQL statements parsed from ``objective_2.sql``.
        Expected (in order) to answer:
            [0] SELECT * FROM order_details
            [1] MIN/MAX order_date (date range)
            [2] total distinct orders
            [3] total dishes ordered (row count)
            [4] order with the most dishes
            [5] all orders with >= 13 dishes
        As with Objective 1, any missing statement falls back to a safe
        inline equivalent so the report is always complete.

    Returns
    -------
    OrderAnalysisResult
        Structured bundle of every DataFrame/metric produced by this
        objective.
    """
    logger.info("Running Objective 2: Order Data Analysis...")

    def _query_or_fallback(index: int, fallback_sql: str) -> pd.DataFrame:
        if index < len(objective_2_queries):
            return run_named_query(connection, objective_2_queries[index])
        return run_named_query(connection, fallback_sql)

    order_details = _query_or_fallback(0, "SELECT * FROM order_details;")

    date_range_df = _query_or_fallback(
        1,
        "SELECT MIN(order_date) AS first_date, MAX(order_date) AS last_date "
        "FROM order_details;",
    )
    first_order_date = str(date_range_df.iloc[0]["first_date"])
    last_order_date = str(date_range_df.iloc[0]["last_date"])

    total_orders_df = _query_or_fallback(
        2,
        "SELECT COUNT(DISTINCT(order_id)) AS total_orders "
        "FROM order_details;",
    )
    total_orders = int(total_orders_df.iloc[0, 0])

    total_dishes_df = _query_or_fallback(
        3, "SELECT COUNT(*) AS total_dishes FROM order_details;"
    )
    total_dishes_ordered = int(total_dishes_df.iloc[0, 0])

    busiest_order = _query_or_fallback(
        4,
        "SELECT order_id, COUNT(item_id) AS total_items "
        "FROM order_details GROUP BY order_id "
        "ORDER BY COUNT(item_id) DESC LIMIT 1;",
    )

    large_orders = _query_or_fallback(
        5,
        "SELECT order_id, COUNT(item_id) AS total_items "
        "FROM order_details GROUP BY order_id "
        "HAVING total_items >= 13;",
    )

    # The day-by-day trend and the derived "average orders per day" metric
    # are computed directly in Python/pandas (rather than pulled from the
    # objective_2.sql file) because they combine a SQL aggregation step
    # with a small amount of date-arithmetic that is most naturally
    # expressed with pandas' datetime tooling.
    orders_per_day = run_named_query(
        connection,
        "SELECT order_date, COUNT(DISTINCT order_id) AS number_of_orders "
        "FROM order_details GROUP BY order_date ORDER BY order_date;",
    )

    span_days = (
        pd.to_datetime(last_order_date) - pd.to_datetime(first_order_date)
    ).days + 1
    average_orders_per_day = total_orders / span_days if span_days else 0.0

    logger.info(
        "Objective 2 complete: %d orders (%d line items) spanning %s to %s.",
        total_orders,
        total_dishes_ordered,
        first_order_date,
        last_order_date,
    )

    return OrderAnalysisResult(
        order_details=order_details,
        first_order_date=first_order_date,
        last_order_date=last_order_date,
        total_orders=total_orders,
        total_dishes_ordered=total_dishes_ordered,
        busiest_order=busiest_order,
        large_orders=large_orders,
        orders_per_day=orders_per_day,
        average_orders_per_day=average_orders_per_day,
    )


# ==============================================================================
# SECTION 5: OBJECTIVE 3 — COMBINED CUSTOMER BEHAVIOUR ANALYSIS
# ==============================================================================
#
# Business question this objective answers:
#   "Once we join menu data to order data, what do we learn about actual
#    customer preferences and spending patterns?"
#
# We explore:
#   1. A joined view of order_details + menu_items (every line item,
#      enriched with its dish name, category and price).
#   2. The least- and most-frequently ordered dishes.
#   3. The 10 highest-value orders by total spend.
#   4. A category-level breakdown of what was ordered in the single
#      highest-spending order.
#   5. A category-level breakdown of what was ordered across the top 5
#      highest-spending orders, to see whether big spenders lean toward
#      any particular cuisine.


def analyze_customer_behavior(
    connection: sqlite3.Connection, objective_3_queries: List[str]
) -> CustomerBehaviorResult:
    """
    Run the full Objective 3 (combined menu + order) analysis.

    Parameters
    ----------
    connection : sqlite3.Connection
        Open connection to the populated in-memory database.
    objective_3_queries : List[str]
        Ordered list of SQL statements parsed from ``objective_3.sql``.
        Expected (in order) to answer:
            [0] order_details LEFT JOIN menu_items (combined view)
            [1] least ordered items (ascending purchase count)
            [2] most ordered items (descending purchase count)
            [3] top 10 orders by total spend
            [4] category breakdown for the single highest-spend order
            [5] category breakdown for the top 5 highest-spend orders
        As with the previous objectives, any missing statement falls
        back to a safe inline equivalent.

    Returns
    -------
    CustomerBehaviorResult
        Structured bundle of every DataFrame produced by this objective.
    """
    logger.info("Running Objective 3: Combined Customer Behaviour Analysis...")

    def _query_or_fallback(index: int, fallback_sql: str) -> pd.DataFrame:
        if index < len(objective_3_queries):
            return run_named_query(connection, objective_3_queries[index])
        return run_named_query(connection, fallback_sql)

    combined = _query_or_fallback(
        0,
        "SELECT * FROM order_details od "
        "LEFT JOIN menu_items mi ON od.item_id = mi.menu_item_id;",
    )

    least_ordered_items = _query_or_fallback(
        1,
        "SELECT item_name, category, COUNT(order_details_id) AS total_purchase "
        "FROM order_details od LEFT JOIN menu_items mi "
        "ON od.item_id = mi.menu_item_id "
        "GROUP BY item_name, category ORDER BY total_purchase ASC;",
    )

    most_ordered_items = _query_or_fallback(
        2,
        "SELECT item_name, category, COUNT(order_details_id) AS total_purchase "
        "FROM order_details od LEFT JOIN menu_items mi "
        "ON od.item_id = mi.menu_item_id "
        "GROUP BY item_name, category ORDER BY total_purchase DESC;",
    )

    top_spending_orders = _query_or_fallback(
        3,
        "SELECT order_id, SUM(price) AS total_order_price "
        "FROM order_details od LEFT JOIN menu_items mi "
        "ON od.item_id = mi.menu_item_id "
        "GROUP BY order_id ORDER BY total_order_price DESC LIMIT 10;",
    )

    # The single highest-spending order's ID is derived dynamically from
    # the top_spending_orders result above, rather than being hard-coded,
    # so this script remains correct even if the underlying seed data
    # (and therefore the identity of the "top" order) ever changes.
    top_order_id = int(top_spending_orders.iloc[0]["order_id"])

    top_order_breakdown = _query_or_fallback(
        4,
        "SELECT category, COUNT(item_id) AS num_items "
        "FROM order_details od LEFT JOIN menu_items mi "
        f"ON od.item_id = mi.menu_item_id WHERE order_id = {top_order_id} "
        "GROUP BY category;",
    )

    top_5_order_ids = tuple(top_spending_orders["order_id"].head(5).tolist())
    top_5_orders_breakdown = _query_or_fallback(
        5,
        "SELECT order_id, category, COUNT(item_id) AS num_items "
        "FROM order_details od LEFT JOIN menu_items mi "
        f"ON od.item_id = mi.menu_item_id WHERE order_id IN {top_5_order_ids} "
        "GROUP BY order_id, category;",
    )

    logger.info(
        "Objective 3 complete: combined view has %d rows; top order is #%d.",
        len(combined),
        top_order_id,
    )

    return CustomerBehaviorResult(
        combined=combined,
        least_ordered_items=least_ordered_items,
        most_ordered_items=most_ordered_items,
        top_spending_orders=top_spending_orders,
        top_order_breakdown=top_order_breakdown,
        top_5_orders_breakdown=top_5_orders_breakdown,
    )


# ==============================================================================
# SECTION 6: VISUALISATION LAYER
# ==============================================================================
#
# All plotting logic lives in this section, cleanly separated from the
# data-analysis logic above. Every chart is saved as a PNG file inside
# the configured output directory rather than being shown interactively,
# so this script behaves identically in a terminal, a Docker container,
# or a CI pipeline where there is no display available.


def _ensure_output_dir(output_dir: Path) -> None:
    """Create the output directory (and parents) if it does not exist."""
    output_dir.mkdir(parents=True, exist_ok=True)


def plot_dishes_per_category(result: MenuAnalysisResult, output_dir: Path) -> None:
    """Bar chart: number of menu dishes offered per category."""
    plt.figure(figsize=(7, 5))
    ax = sns.barplot(
        data=result.dishes_per_category,
        x="category",
        y="total_dishes",
        hue="category",
        palette="Set1",
        legend=False,
    )
    for bar in ax.patches:
        bar.set_width(0.6)
    plt.title("Number of Menu Dishes per Category")
    plt.xlabel("Category")
    plt.ylabel("Total Dishes")
    plt.tight_layout()
    plt.savefig(output_dir / "01_dishes_per_category.png", dpi=150)
    plt.close()


def plot_avg_price_per_category(result: MenuAnalysisResult, output_dir: Path) -> None:
    """Bar chart: average dish price per menu category."""
    plt.figure(figsize=(7, 5))
    ax = sns.barplot(
        data=result.avg_price_per_category,
        x="category",
        y="avg_price",
        hue="category",
        palette="Set1",
        legend=False,
    )
    for bar in ax.patches:
        bar.set_width(0.6)
    plt.title("Average Dish Price per Category")
    plt.xlabel("Category")
    plt.ylabel("Average Price ($)")
    plt.tight_layout()
    plt.savefig(output_dir / "02_avg_price_per_category.png", dpi=150)
    plt.close()


def plot_orders_over_time(result: OrderAnalysisResult, output_dir: Path) -> None:
    """Line chart: number of distinct orders placed per calendar day."""
    plt.figure(figsize=(12, 5))
    plt.plot(
        pd.to_datetime(result.orders_per_day["order_date"]),
        result.orders_per_day["number_of_orders"],
        marker="o",
        markersize=3,
        linewidth=1,
    )
    plt.title("Daily Order Volume Trend")
    plt.xlabel("Date")
    plt.ylabel("Number of Orders")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "03_orders_over_time.png", dpi=150)
    plt.close()


def plot_top_10_orders(result: CustomerBehaviorResult, output_dir: Path) -> None:
    """Bar chart: the 10 orders that generated the most revenue."""
    plt.figure(figsize=(9, 5))
    data = result.top_spending_orders.copy()
    data["order_id"] = data["order_id"].astype(str)
    ax = sns.barplot(
        data=data,
        x="order_id",
        y="total_order_price",
        hue="order_id",
        palette="viridis",
        legend=False,
    )
    plt.title("Top 10 Orders by Total Spend")
    plt.xlabel("Order ID")
    plt.ylabel("Total Order Price ($)")
    plt.tight_layout()
    plt.savefig(output_dir / "04_top_10_orders.png", dpi=150)
    plt.close()


def plot_least_and_most_ordered(
    result: CustomerBehaviorResult, output_dir: Path
) -> None:
    """Side-by-side horizontal bar charts: least vs. most ordered dishes."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))

    least = result.least_ordered_items.dropna(subset=["item_name"]).head(10)
    most = result.most_ordered_items.dropna(subset=["item_name"]).head(10)

    sns.barplot(
        data=least, x="total_purchase", y="item_name", ax=axes[0],
        hue="item_name", palette="coolwarm", legend=False,
    )
    axes[0].set_title("Least Ordered Items (Top 10)")
    axes[0].set_xlabel("Total Purchases")
    axes[0].set_ylabel("Item Name")

    sns.barplot(
        data=most, x="total_purchase", y="item_name", ax=axes[1],
        hue="item_name", palette="viridis", legend=False,
    )
    axes[1].set_title("Most Ordered Items (Top 10)")
    axes[1].set_xlabel("Total Purchases")
    axes[1].set_ylabel("Item Name")

    plt.tight_layout()
    plt.savefig(output_dir / "05_least_and_most_ordered_items.png", dpi=150)
    plt.close()


def plot_top_order_category_breakdown(
    result: CustomerBehaviorResult, output_dir: Path
) -> None:
    """Bar chart: category composition of the single highest-spend order."""
    plt.figure(figsize=(7, 5))
    ax = sns.barplot(
        data=result.top_order_breakdown,
        x="category",
        y="num_items",
        hue="category",
        palette="rainbow",
        legend=False,
    )
    plt.title("Highest-Spend Order — Items by Category")
    plt.xlabel("Category")
    plt.ylabel("Number of Items")
    plt.tight_layout()
    plt.savefig(output_dir / "06_top_order_category_breakdown.png", dpi=150)
    plt.close()


def plot_top_5_orders_category_breakdown(
    result: CustomerBehaviorResult, output_dir: Path
) -> None:
    """Grouped bar chart: category composition across the top 5 orders."""
    plt.figure(figsize=(9, 5))
    data = result.top_5_orders_breakdown.copy()
    data["order_id"] = data["order_id"].astype(str)
    sns.barplot(
        data=data, x="order_id", y="num_items", hue="category",
    )
    plt.title("Top 5 Highest-Spend Orders — Items by Category")
    plt.xlabel("Order ID")
    plt.ylabel("Number of Items")
    plt.legend(title="Category")
    plt.tight_layout()
    plt.savefig(output_dir / "07_top_5_orders_category_breakdown.png", dpi=150)
    plt.close()


def generate_all_visualizations(report: AnalysisReport, output_dir: Path) -> None:
    """
    Orchestrate the generation of every chart described in this script,
    saving each one as a standalone PNG inside ``output_dir``.

    If matplotlib/seaborn are not installed, this function logs a
    warning and returns immediately rather than raising — plotting is
    treated as a "nice to have" enhancement on top of the core, purely
    tabular SQL analysis, not a hard requirement to run the pipeline.
    """
    if not _PLOTTING_AVAILABLE:
        logger.warning(
            "matplotlib/seaborn are not installed — skipping chart "
            "generation. Install them with `pip install matplotlib seaborn` "
            "to enable this feature."
        )
        return

    _ensure_output_dir(output_dir)
    sns.set_theme(style="whitegrid")

    plot_dishes_per_category(report.menu, output_dir)
    plot_avg_price_per_category(report.menu, output_dir)
    plot_orders_over_time(report.orders, output_dir)
    plot_top_10_orders(report.behavior, output_dir)
    plot_least_and_most_ordered(report.behavior, output_dir)
    plot_top_order_category_breakdown(report.behavior, output_dir)
    plot_top_5_orders_category_breakdown(report.behavior, output_dir)

    logger.info("All charts saved to '%s'.", output_dir)


# ==============================================================================
# SECTION 7: HUMAN-READABLE REPORT PRINTING
# ==============================================================================
#
# The functions in this section are responsible only for *presentation*.
# They take already-computed results and format them for a terminal
# reader. Keeping this separate from the analysis functions above means
# the analysis functions can be reused (e.g. imported into a Jupyter
# notebook, a Flask API, or a unit test) without dragging along any
# print formatting.


def _section_header(title: str) -> None:
    """Print a visually distinct section header to stdout."""
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def print_menu_report(result: MenuAnalysisResult) -> None:
    """Print a full, human-readable summary of the Objective 1 results."""
    _section_header("OBJECTIVE 1 — MENU ITEMS ANALYSIS")

    print(f"\nTotal menu items on offer: {result.total_items}")

    print("\nCheapest dish overall:")
    print(result.cheapest_dish.to_string(index=False))

    print("\nMost expensive dish overall:")
    print(result.most_expensive_dish.to_string(index=False))

    print(f"\nTotal Italian dishes: {result.total_italian_dishes}")

    print("\nCheapest Italian dish:")
    print(result.cheapest_italian_dish.to_string(index=False))

    print("\nMost expensive Italian dish:")
    print(result.most_expensive_italian_dish.to_string(index=False))

    print("\nNumber of dishes per category:")
    print(result.dishes_per_category.to_string(index=False))

    print("\nAverage price per category:")
    formatted = result.avg_price_per_category.copy()
    if "avg_price" in formatted.columns:
        formatted["avg_price"] = formatted["avg_price"].round(2)
    print(formatted.to_string(index=False))


def print_orders_report(result: OrderAnalysisResult) -> None:
    """Print a full, human-readable summary of the Objective 2 results."""
    _section_header("OBJECTIVE 2 — ORDER DATA ANALYSIS")

    print(f"\nOrder data spans: {result.first_order_date} to {result.last_order_date}")
    print(f"Total distinct orders placed: {result.total_orders}")
    print(f"Total individual dishes ordered (line items): {result.total_dishes_ordered}")
    print(f"Average orders placed per day: {result.average_orders_per_day:.2f}")

    print("\nOrder with the most individual dishes:")
    print(result.busiest_order.to_string(index=False))

    print(f"\nOrders containing 13 or more dishes ({len(result.large_orders)} found):")
    print(result.large_orders.to_string(index=False))


def print_behavior_report(result: CustomerBehaviorResult) -> None:
    """Print a full, human-readable summary of the Objective 3 results."""
    _section_header("OBJECTIVE 3 — CUSTOMER BEHAVIOUR ANALYSIS")

    print("\nTop 5 least ordered dishes:")
    print(result.least_ordered_items.head(5).to_string(index=False))

    print("\nTop 5 most ordered dishes:")
    print(result.most_ordered_items.head(5).to_string(index=False))

    print("\nTop 10 highest-spend orders:")
    print(result.top_spending_orders.to_string(index=False))

    top_order_id = int(result.top_spending_orders.iloc[0]["order_id"])
    print(f"\nCategory breakdown of the single highest-spend order (#{top_order_id}):")
    print(result.top_order_breakdown.to_string(index=False))

    print("\nCategory breakdown across the top 5 highest-spend orders:")
    print(result.top_5_orders_breakdown.to_string(index=False))


def print_full_report(report: AnalysisReport) -> None:
    """Print the complete, three-objective analysis report to stdout."""
    print("\n" + "#" * 78)
    print("#  INDICA CAFE — FULL DATA ANALYSIS REPORT")
    print("#" * 78)

    print_menu_report(report.menu)
    print_orders_report(report.orders)
    print_behavior_report(report.behavior)

    print("\n" + "#" * 78)
    print("#  END OF REPORT")
    print("#" * 78 + "\n")


# ==============================================================================
# SECTION 8: PIPELINE ORCHESTRATION
# ==============================================================================


def load_all_sql_assets(data_dir: Path) -> Dict[str, object]:
    """
    Locate and parse every ``.sql`` asset this script depends on.

    Parameters
    ----------
    data_dir : Path
        Directory expected to contain ``create_restaurant_db.sql``,
        ``objective_1.sql``, ``objective_2.sql`` and ``objective_3.sql``.

    Returns
    -------
    Dict[str, object]
        A dictionary with the following keys:
            "schema_sql"        -> raw schema/seed-data SQL text (str)
            "objective_1_queries" -> parsed statement list (List[str])
            "objective_2_queries" -> parsed statement list (List[str])
            "objective_3_queries" -> parsed statement list (List[str])
    """
    logger.info("Loading SQL assets from '%s'...", data_dir)

    schema_sql = read_sql_file(data_dir / SCHEMA_FILE)

    objective_1_sql = read_sql_file(data_dir / OBJECTIVE_1_FILE)
    objective_2_sql = read_sql_file(data_dir / OBJECTIVE_2_FILE)
    objective_3_sql = read_sql_file(data_dir / OBJECTIVE_3_FILE)

    return {
        "schema_sql": schema_sql,
        "objective_1_queries": split_sql_statements(objective_1_sql),
        "objective_2_queries": split_sql_statements(objective_2_sql),
        "objective_3_queries": split_sql_statements(objective_3_sql),
    }


def run_full_analysis(data_dir: Path) -> AnalysisReport:
    """
    Execute the complete, three-objective analysis pipeline end to end:

        1. Load and parse all required ``.sql`` assets from disk.
        2. Build and seed an in-memory SQLite database from the schema.
        3. Run each objective's analysis in turn.
        4. Bundle the three objective results into a single report.

    Parameters
    ----------
    data_dir : Path
        Directory containing the ``.sql`` source files.

    Returns
    -------
    AnalysisReport
        The fully populated, three-objective analysis report.
    """
    assets = load_all_sql_assets(data_dir)

    connection = build_in_memory_database(assets["schema_sql"])

    tables = list_tables(connection)
    logger.info("Tables detected in database: %s", ", ".join(tables["name"]))

    try:
        menu_result = analyze_menu_items(connection, assets["objective_1_queries"])
        order_result = analyze_orders(connection, assets["objective_2_queries"])
        behavior_result = analyze_customer_behavior(
            connection, assets["objective_3_queries"]
        )
    finally:
        connection.close()
        logger.info("Database connection closed.")

    return AnalysisReport(
        menu=menu_result, orders=order_result, behavior=behavior_result
    )


# ==============================================================================
# SECTION 9: COMMAND-LINE INTERFACE
# ==============================================================================


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments controlling where data is read from,
    where output is written to, and whether chart generation should run.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Run the full Indica Cafe menu/order/customer-behaviour "
            "analysis pipeline against the SQL assets in the data "
            "directory, printing a report and (optionally) saving charts."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=(
            "Path to the folder containing create_restaurant_db.sql, "
            "objective_1.sql, objective_2.sql and objective_3.sql "
            f"(default: '{DEFAULT_DATA_DIR}')."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save generated charts into (default: '{DEFAULT_OUTPUT_DIR}').",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip chart generation entirely and only print the text report.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """
    Script entry point.

    Returns
    -------
    int
        Process exit code: 0 on success, 1 on failure. Returning an int
        (rather than calling ``sys.exit`` directly) keeps this function
        easily unit-testable.
    """
    args = parse_arguments(argv)

    try:
        report = run_full_analysis(args.data_dir)
    except Exception as exc:  # noqa: BLE001 - top-level guard for a CLI tool
        logger.error("Analysis pipeline failed: %s", exc)
        return 1

    print_full_report(report)

    if not args.no_plots:
        generate_all_visualizations(report, args.output_dir)
    else:
        logger.info("Chart generation skipped (--no-plots supplied).")

    logger.info("Analysis pipeline finished successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
