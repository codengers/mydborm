# =============================================================================
# File        : cli.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Author      : Atikrant Upadhye
# Created     : 2026-06-15
# Version     : 0.2.0
# License     : MIT
# Description : Command-line interface built with Typer. Provides
#               terminal commands: mydborm version, mydborm inspect,
#               mydborm shell, mydborm ping.
#               Install: pip install mydborm[cli]
# =============================================================================

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

cli     = typer.Typer(
    name="mydborm",
    help="mydborm — Lightweight ORM for MySQL and YugabyteDB",
    add_completion=False,
)
console = Console()


# ------------------------------------------------------------------ #
#  version                                                             #
# ------------------------------------------------------------------ #

@cli.command()
def version():
    """Show mydborm version and supported databases."""
    from mydborm import __version__, __author__
    console.print(Panel(
        f"[bold cyan]mydborm[/bold cyan] v{__version__}\n"
        f"[dim]Author  : {__author__}[/dim]\n"
        f"[dim]License : MIT[/dim]\n"
        f"[dim]Supports: MySQL 8+ | YugabyteDB (YSQL)[/dim]",
        title="[bold green]mydborm CLI[/bold green]",
        border_style="green",
    ))


# ------------------------------------------------------------------ #
#  ping                                                                #
# ------------------------------------------------------------------ #

@cli.command()
def ping(
    dialect:  str = typer.Option("mysql",     "--dialect",  "-d", help="mysql or yugabyte"),
    host:     str = typer.Option("127.0.0.1", "--host",     "-h", help="Database host"),
    port:     int = typer.Option(3306,        "--port",     "-p", help="Database port"),
    user:     str = typer.Option("root",      "--user",     "-u", help="Database user"),
    password: str = typer.Option("",          "--password", "-w", help="Database password", hide_input=True),
    database: str = typer.Option("testdb",    "--database", "-n", help="Database name"),
):
    """Test database connectivity and show server info."""
    from mydborm.db import db

    console.print(f"\n[cyan]Connecting to[/cyan] [bold]{dialect}[/bold] "
                  f"at [bold]{host}:{port}[/bold] ...")

    try:
        db.configure(
            dialect=dialect, host=host, port=port,
            user=user, password=password, database=database
        )
        with db.connect() as conn:
            cur = conn.cursor()

            if dialect == "mysql":
                cur.execute("SELECT VERSION(), DATABASE(), USER()")
                row = cur.fetchone()
                t = Table(box=box.ROUNDED, border_style="green")
                t.add_column("Property", style="cyan")
                t.add_column("Value",    style="white")
                t.add_row("Status",   "[bold green]✔ Connected[/bold green]")
                t.add_row("Dialect",  dialect)
                t.add_row("Version",  row[0])
                t.add_row("Database", row[1])
                t.add_row("User",     row[2])
            else:
                cur.execute("SELECT VERSION(), current_database(), current_user")
                row = cur.fetchone()
                t = Table(box=box.ROUNDED, border_style="green")
                t.add_column("Property", style="cyan")
                t.add_column("Value",    style="white")
                t.add_row("Status",   "[bold green]✔ Connected[/bold green]")
                t.add_row("Dialect",  dialect)
                t.add_row("Version",  row[0])
                t.add_row("Database", row[1])
                t.add_row("User",     row[2])

            console.print(t)
        db.close()

    except Exception as e:
        console.print(f"\n[bold red]✘ Connection failed:[/bold red] {e}\n")
        raise typer.Exit(code=1)


# ------------------------------------------------------------------ #
#  inspect                                                             #
# ------------------------------------------------------------------ #

@cli.command()
def inspect(
    dialect:  str = typer.Option("mysql",     "--dialect",  "-d"),
    host:     str = typer.Option("127.0.0.1", "--host",     "-h"),
    port:     int = typer.Option(3306,        "--port",     "-p"),
    user:     str = typer.Option("root",      "--user",     "-u"),
    password: str = typer.Option("",          "--password", "-w", hide_input=True),
    database: str = typer.Option("testdb",    "--database", "-n"),
):
    """Inspect all tables and columns in the connected database."""
    from mydborm.db import db

    try:
        db.configure(
            dialect=dialect, host=host, port=port,
            user=user, password=password, database=database
        )
        with db.connect() as conn:
            cur = conn.cursor()

            # Get all tables
            if dialect == "mysql":
                cur.execute("SHOW TABLES;")
                tables = [row[0] for row in cur.fetchall()]
            else:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cur.fetchall()]

            if not tables:
                console.print(
                    f"\n[yellow]No tables found in database "
                    f"'{database}'.[/yellow]\n"
                )
                return

            console.print(
                f"\n[bold cyan]Database:[/bold cyan] {database}  "
                f"[bold cyan]Dialect:[/bold cyan] {dialect}  "
                f"[bold cyan]Tables:[/bold cyan] {len(tables)}\n"
            )

            for table in tables:
                # Get columns
                if dialect == "mysql":
                    cur.execute(f"DESCRIBE `{table}`;")
                    rows = cur.fetchall()
                    t = Table(
                        title=f"[bold]{table}[/bold]",
                        box=box.SIMPLE_HEAVY,
                        border_style="cyan",
                        show_lines=True,
                    )
                    t.add_column("Column",  style="bold white")
                    t.add_column("Type",    style="yellow")
                    t.add_column("Null",    style="dim")
                    t.add_column("Key",     style="green")
                    t.add_column("Default", style="dim")
                    for row in rows:
                        t.add_row(
                            str(row[0]), str(row[1]),
                            str(row[2]), str(row[3]),
                            str(row[4]) if row[4] else "-"
                        )
                else:
                    cur.execute(f"""
                        SELECT column_name, data_type, is_nullable,
                               column_default
                        FROM information_schema.columns
                        WHERE table_name = '{table}'
                        ORDER BY ordinal_position;
                    """)
                    rows = cur.fetchall()
                    t = Table(
                        title=f"[bold]{table}[/bold]",
                        box=box.SIMPLE_HEAVY,
                        border_style="cyan",
                        show_lines=True,
                    )
                    t.add_column("Column",   style="bold white")
                    t.add_column("Type",     style="yellow")
                    t.add_column("Nullable", style="dim")
                    t.add_column("Default",  style="dim")
                    for row in rows:
                        t.add_row(
                            str(row[0]), str(row[1]),
                            str(row[2]),
                            str(row[3]) if row[3] else "-"
                        )

                console.print(t)

        db.close()

    except Exception as e:
        console.print(f"\n[bold red]✘ Error:[/bold red] {e}\n")
        raise typer.Exit(code=1)


# ------------------------------------------------------------------ #
#  tables                                                              #
# ------------------------------------------------------------------ #

@cli.command()
def tables(
    dialect:  str = typer.Option("mysql",     "--dialect",  "-d"),
    host:     str = typer.Option("127.0.0.1", "--host",     "-h"),
    port:     int = typer.Option(3306,        "--port",     "-p"),
    user:     str = typer.Option("root",      "--user",     "-u"),
    password: str = typer.Option("",          "--password", "-w", hide_input=True),
    database: str = typer.Option("testdb",    "--database", "-n"),
):
    """List all tables in the connected database."""
    from mydborm.db import db

    try:
        db.configure(
            dialect=dialect, host=host, port=port,
            user=user, password=password, database=database
        )
        with db.connect() as conn:
            cur = conn.cursor()

            if dialect == "mysql":
                cur.execute("SHOW TABLES;")
            else:
                cur.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)

            rows = cur.fetchall()

            t = Table(
                title=f"Tables in [bold]{database}[/bold]",
                box=box.ROUNDED,
                border_style="cyan",
            )
            t.add_column("#",     style="dim", width=4)
            t.add_column("Table", style="bold white")

            for i, row in enumerate(rows, 1):
                t.add_row(str(i), row[0])

            console.print()
            console.print(t)
            console.print(
                f"\n[dim]{len(rows)} table(s) found.[/dim]\n"
            )

        db.close()

    except Exception as e:
        console.print(f"\n[bold red]✘ Error:[/bold red] {e}\n")
        raise typer.Exit(code=1)


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    cli()





