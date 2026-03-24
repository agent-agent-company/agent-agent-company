"""
AAC Protocol User CLI

Command line interface for users.
"""

import asyncio
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

console = Console()


@click.group()
def main():
    """AAC Protocol User CLI"""
    pass


@main.command()
def init():
    """Initialize user environment"""
    console.print(Panel(
        "[green]Welcome to AAC Protocol User CLI[/green]\n\n"
        "This tool helps you discover and work with agents on the AAC Protocol network.\n\n"
        "Your account has been initialized with: [cyan]1,000 AAC tokens[/cyan]\n\n"
        "Get started by:\n"
        "  1. Discover agents: [cyan]aac-user discover[/cyan]\n"
        "  2. Submit a task: [cyan]aac-user submit-task[/cyan]",
        title="AAC Protocol",
        border_style="blue"
    ))


@main.command()
@click.option('--keyword', '-k', multiple=True, help='Search keywords')
@click.option('--min-trust', type=float, help='Minimum trust score')
@click.option('--max-price', type=float, help='Maximum price')
@click.option('--sort', default='trust_score', type=click.Choice(['trust_score', 'price', 'name']))
def discover(keyword, min_trust, max_price, sort):
    """Discover available agents"""
    console.print("[blue]Discovering agents...[/blue]\n")
    
    table = Table(title="Available Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description", style="white", max_width=40)
    table.add_column("Price", style="magenta")
    table.add_column("Trust", style="blue")
    table.add_column("Rating", style="yellow")
    
    # Mock data - would query registry
    table.add_row(
        "weather-001",
        "Weather Agent",
        "Provides weather forecasts for any location",
        "2.0 AAC",
        "85.5",
        "4.5"
    )
    table.add_row(
        "translate-001",
        "Translation Agent",
        "Translates text between 50+ languages",
        "3.0 AAC",
        "72.3",
        "4.2"
    )
    table.add_row(
        "data-001",
        "Data Analyst",
        "Analyzes data and generates insights",
        "5.0 AAC",
        "91.2",
        "4.8"
    )
    
    console.print(table)


@main.command()
@click.option('--agent-id', prompt='Agent ID', help='Target agent ID')
@click.option('--content', prompt='Task content', help='Task description')
@click.option('--mode', default='balanced', type=click.Choice(['performance', 'price', 'balanced']))
def submit_task(agent_id, content, mode):
    """Submit a task to an agent"""
    console.print(f"[blue]Submitting task to {agent_id}...[/blue]")
    console.print(f"Mode: {mode}")
    console.print(f"Content: {content}\n")
    
    with Progress() as progress:
        task = progress.add_task("[cyan]Processing...", total=100)
        
        # Simulate task processing
        for i in range(10):
            progress.update(task, advance=10)
            asyncio.run(asyncio.sleep(0.1))
    
    console.print("\n[green]Task completed successfully![/green]")
    console.print("Task ID: task-abc123def456")
    console.print("Cost: 2.5 AAC tokens")


@main.command()
def balance():
    """Check token balance"""
    console.print(Panel(
        "[green]Account Balance[/green]\n\n"
        "Current Balance: [cyan]985.5 AAC[/cyan]\n"
        "Locked (in tasks): [yellow]14.5 AAC[/cyan]\n"
        "Available: [green]971.0 AAC[/cyan]\n\n"
        "Total Spent: [red]14.5 AAC[/cyan]\n"
        "Tasks Completed: [blue]5[/blue]",
        title="Balance",
        border_style="cyan"
    ))


@main.command()
def history():
    """View transaction history"""
    table = Table(title="Transaction History")
    table.add_column("Time", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Amount", style="magenta")
    table.add_column("Status", style="yellow")
    table.add_column("Details", style="white")
    
    # Mock data
    table.add_row(
        "2024-01-15 10:30",
        "Payment",
        "-2.5 AAC",
        "Completed",
        "Task: weather-001"
    )
    table.add_row(
        "2024-01-14 15:45",
        "Payment",
        "-3.0 AAC",
        "Completed",
        "Task: translate-001"
    )
    table.add_row(
        "2024-01-13 09:20",
        "Refund",
        "+1.0 AAC",
        "Completed",
        "Task cancelled"
    )
    
    console.print(table)


@main.command()
@click.argument('task_id')
def rate_task(task_id):
    """Rate a completed task"""
    rating = click.prompt('Rating (1-5)', type=int)
    feedback = click.prompt('Feedback (optional)', default='')
    
    console.print(f"\n[green]Task {task_id} rated: {rating}/5[/green]")
    if feedback:
        console.print(f"Feedback: {feedback}")


@main.command()
@click.argument('task_id')
def file_dispute(task_id):
    """File a dispute for a task"""
    console.print(f"[yellow]Filing dispute for task: {task_id}[/yellow]\n")
    
    claim = click.prompt('Describe your complaint')
    amount = click.prompt('Compensation amount (AAC)', type=float)
    
    console.print(f"\n[blue]Dispute Details:[/blue]")
    console.print(f"  Task: {task_id}")
    console.print(f"  Claim: {claim}")
    console.print(f"  Amount: {amount} AAC")
    
    if click.confirm('\nSubmit dispute?'):
        console.print("\n[green]Dispute filed successfully![/green]")
        console.print("Dispute ID: dispute-xyz789")
        console.print("Status: Pending review")
    else:
        console.print("[yellow]Dispute cancelled[/yellow]")


@main.command()
def tasks():
    """View your tasks"""
    table = Table(title="Your Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Agent", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Cost", style="magenta")
    table.add_column("Submitted", style="blue")
    
    table.add_row("task-001", "weather-001", "Completed", "2.5 AAC", "2024-01-15")
    table.add_row("task-002", "translate-001", "Completed", "3.0 AAC", "2024-01-14")
    table.add_row("task-003", "data-001", "In Progress", "5.0 AAC", "2024-01-15")
    table.add_row("task-004", "weather-001", "Pending", "2.5 AAC", "2024-01-15")
    
    console.print(table)


if __name__ == "__main__":
    main()
