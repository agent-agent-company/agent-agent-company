"""
AAC Protocol Example: Weather Agent

A simple example agent that provides weather information.
"""

import asyncio
import random
from datetime import datetime

from aac_protocol.core.models import AgentCard, AgentID, TaskInput, TaskOutput
from aac_protocol.creator.sdk.agent import Agent, AgentCapability
from aac_protocol.creator.sdk.card import AgentCardBuilder


class WeatherAgent(Agent):
    """
    Example weather agent
    
    Provides weather forecasts for locations.
    """
    
    def __init__(self, creator_id: str, creator_name: str = "Demo Creator"):
        # Build agent card
        card = AgentCardBuilder("weather", None) \
            .with_id(1) \
            .with_description(
                "Provides accurate weather forecasts for any location worldwide. "
                "Supports current conditions, hourly forecasts, and 7-day predictions."
            ) \
            .with_price(2.0) \
            .with_capability("weather-forecast") \
            .with_capability("current-conditions") \
            .with_capability("hourly-prediction") \
            .accepts_input("text") \
            .accepts_input("location") \
            .produces_output("text") \
            .produces_output("json") \
            .at_endpoint("http://localhost:8001") \
            .build()
        
        # Set creator info
        card.creator_id = creator_id
        card.creator_name = creator_name
        
        # Define capabilities
        capabilities = [
            AgentCapability(
                "weather-forecast",
                "Get weather forecast for a location",
                input_schema={"location": "string", "days": "integer"},
                output_schema={"forecast": "array", "location": "object"},
            ),
            AgentCapability(
                "current-conditions",
                "Get current weather conditions",
                input_schema={"location": "string"},
                output_schema={"temperature": "number", "conditions": "string"},
            ),
        ]
        
        super().__init__(card, capabilities)
    
    async def execute_task(self, task_input: TaskInput) -> TaskOutput:
        """
        Execute weather query
        
        Simulates weather data - in production, would call weather API.
        """
        location = task_input.content.strip()
        
        # Simulate weather data
        conditions = random.choice([
            "Sunny", "Partly Cloudy", "Cloudy", "Light Rain",
            "Heavy Rain", "Snow", "Thunderstorm"
        ])
        
        temp = random.randint(-10, 35)
        
        # Generate forecast
        forecast = []
        for i in range(7):
            day_temp = temp + random.randint(-5, 5)
            day_cond = random.choice([
                "Sunny", "Partly Cloudy", "Cloudy", "Light Rain"
            ])
            forecast.append({
                "day": f"Day {i+1}",
                "temp": day_temp,
                "conditions": day_cond,
            })
        
        # Build response
        response = f"""
Weather Forecast for {location}:

Current Conditions:
  Temperature: {temp}C
  Conditions: {conditions}

7-Day Forecast:
"""
        for day in forecast:
            response += f"  {day['day']}: {day['temp']}C, {day['conditions']}\n"
        
        return TaskOutput(
            content=response.strip(),
            metadata={
                "location": location,
                "current_temp": temp,
                "current_conditions": conditions,
                "forecast": forecast,
                "generated_at": datetime.utcnow().isoformat(),
            }
        )


async def main():
    """Run the weather agent"""
    print("Starting Weather Agent...")
    print("Creator ID: demo-creator-001")
    
    # Create agent
    agent = WeatherAgent("demo-creator-001", "Weather Services Inc.")
    
    # Print agent info
    print(f"\nAgent: {agent.card.name}")
    print(f"ID: {agent.card.id.full_id}")
    print(f"Price: {agent.card.price_per_task} AAC tokens")
    print(f"Capabilities: {', '.join(agent.card.capabilities)}")
    print(f"Endpoint: {agent.card.endpoint_url}")
    
    # Test task
    print("\n--- Test Task ---")
    test_input = TaskInput(content="Tokyo, Japan")
    
    try:
        output = await agent.execute_task(test_input)
        print(output.content)
        print(f"\nMetadata: {output.metadata}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Start server
    print("\n--- Starting Server ---")
    print("Press Ctrl+C to stop")
    
    try:
        await agent.start_server(host="0.0.0.0", port=8001)
    except KeyboardInterrupt:
        print("\nStopping agent...")
        await agent.stop_server()


if __name__ == "__main__":
    asyncio.run(main())
