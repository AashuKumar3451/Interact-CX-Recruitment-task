from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import pytz  # For timezone handling
from collections import Counter

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    city = data['queryResult']['parameters']['city']
    date_param = data['queryResult']['parameters'].get('date', '')
    
    # Get OpenWeather API key (store this securely in production)
    api_key = "2a95869d7db96ee13f7b80a10ec8197c"
    
    # Determine if we need current weather or forecast
    if date_param:
        return handle_date_specific_weather(city, date_param, api_key)
    else:
        return handle_current_weather(city, api_key)

def handle_current_weather(city, api_key):
    """Handle requests for current weather"""
    try:
        current_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
        current_data = requests.get(current_url).json()
        
        if current_data.get('cod') != 200:
            return error_response(f"Could not find weather data for {city}")
        
        weather = current_data['weather'][0]
        main = current_data['main']
        wind = current_data.get('wind', {})
        sys = current_data.get('sys', {})
        
        timezone = pytz.timezone('UTC')  # OpenWeather returns UTC times
        sunrise = datetime.fromtimestamp(sys.get('sunrise', 0), tz=timezone)
        sunset = datetime.fromtimestamp(sys.get('sunset', 0), tz=timezone)
        current_time = datetime.now(timezone)
        
        response = {
            "fulfillmentText": (
                f"Current weather in {city}:\n"
                f"• Condition: {weather['description'].capitalize()}\n"
                f"• Temperature: {main['temp']}°C (feels like {main['feels_like']}°C)\n"
                f"• Humidity: {main['humidity']}%\n"
                f"• Wind: {wind.get('speed', 'N/A')} m/s, {wind.get('deg', 'N/A')}°\n"
                f"• Pressure: {main['pressure']} hPa\n"
                f"• Sunrise: {sunrise.strftime('%H:%M')}\n"
                f"• Sunset: {sunset.strftime('%H:%M')}"
            ),
            "payload": {
                "city": city,
                "temperature": main['temp'],
                "condition": weather['description'],
                "humidity": main['humidity'],
                "wind_speed": wind.get('speed'),
                "wind_direction": wind.get('deg'),
                "sunrise": sunrise.strftime('%H:%M'),
                "sunset": sunset.strftime('%H:%M'),
                "timestamp": current_time.isoformat()
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        return error_response(f"Error fetching weather data: {str(e)}")

def handle_date_specific_weather(city, date_param, api_key):
    """Handle requests for weather on specific dates and times"""
    try:
        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric"
        forecast_data = requests.get(forecast_url).json()
        
        if forecast_data.get('cod') != '200':
            return error_response(f"Could not find forecast data for {city}")
        
        # Parse requested datetime
        try:
            if isinstance(date_param, str) and 'T' in date_param:
                requested_datetime = datetime.strptime(date_param, '%Y-%m-%dT%H:%M:%S%z')
            else:
                requested_datetime = datetime(
                    date_param['year'],
                    date_param['month'],
                    date_param['day'],
                    date_param.get('hours', 0),
                    date_param.get('minutes', 0),
                    tzinfo=pytz.UTC
                )
        except Exception:
            requested_datetime = datetime.now(pytz.UTC)

        requested_date = requested_datetime.date()

        # Find all forecasts for that date
        matching_forecasts = []
        for item in forecast_data['list']:
            forecast_time = datetime.utcfromtimestamp(item['dt']).replace(tzinfo=pytz.UTC)
            if forecast_time.date() == requested_date:
                matching_forecasts.append(item)
        
        if not matching_forecasts:
            return error_response(f"No forecast available for {requested_date.strftime('%Y-%m-%d')}")
        
        # If time is provided, find the closest forecast
        if isinstance(date_param, str) and 'T' in date_param:
            closest_forecast = min(
                matching_forecasts,
                key=lambda x: abs(datetime.utcfromtimestamp(x['dt']).replace(tzinfo=pytz.UTC) - requested_datetime)
            )

            forecast_time = datetime.utcfromtimestamp(closest_forecast['dt']).replace(tzinfo=pytz.UTC)
            weather_desc = closest_forecast['weather'][0]['description']
            temp = closest_forecast['main']['temp']
            
            response_text = (
                f"Weather forecast for {city} on {forecast_time.strftime('%A, %B %d at %H:%M')}:\n"
                f"• Condition: {weather_desc.capitalize()}\n"
                f"• Temperature: {temp:.1f}°C"
            )
            
            return jsonify({
                "fulfillmentText": response_text,
                "payload": {
                    "city": city,
                    "date_time": forecast_time.strftime('%Y-%m-%d %H:%M'),
                    "condition": weather_desc,
                    "temperature": temp
                }
            })
        
        else:
            # Only date provided: calculate daily summary
            temps = [f['main']['temp'] for f in matching_forecasts]
            conditions = [f['weather'][0]['description'] for f in matching_forecasts]
            
            common_condition = Counter(conditions).most_common(1)[0][0]
            
            response_text = (
                f"Weather forecast for {city} on {requested_date.strftime('%A, %B %d')}:\n"
                f"• Expected condition: {common_condition.capitalize()}\n"
                f"• High temperature: {max(temps):.1f}°C\n"
                f"• Low temperature: {min(temps):.1f}°C\n"
                f"• Average temperature: {sum(temps)/len(temps):.1f}°C"
            )
            
            return jsonify({
                "fulfillmentText": response_text,
                "payload": {
                    "city": city,
                    "date": requested_date.strftime('%Y-%m-%d'),
                    "condition": common_condition,
                    "high_temp": max(temps),
                    "low_temp": min(temps),
                    "avg_temp": sum(temps) / len(temps)
                }
            })
        
    except Exception as e:
        return error_response(f"Error processing forecast: {str(e)}")

def error_response(message):
    """Helper function for error responses"""
    return jsonify({
        "fulfillmentText": message,
        "payload": {
            "error": True,
            "message": message
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)