from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import pytz
from collections import Counter

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    city = data['queryResult']['parameters']['city']
    date_param = data['queryResult']['parameters'].get('date', '')
    api_key = "2a95869d7db96ee13f7b80a10ec8197c"
    if date_param:
        return handle_date_specific_weather(city, date_param, api_key)
    else:
        return handle_current_weather(city, api_key)

def handle_current_weather(city, api_key):
    try:
        current_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
        current_data = requests.get(current_url).json()
        if current_data.get('cod') != 200:
            return error_response(f"Could not find weather data for {city}")
        weather = current_data['weather'][0]
        main = current_data['main']
        wind = current_data.get('wind', {})
        sys = current_data.get('sys', {})
        timezone = pytz.timezone('UTC')
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
    try:
        forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric"
        forecast_data = requests.get(forecast_url).json()
        if forecast_data.get('cod') != '200':
            return error_response(f"Could not find forecast data for {city}")
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
        start_date = requested_datetime.date()
        end_date = start_date + timedelta(days=7)
        daily_forecasts = {}
        for item in forecast_data['list']:
            forecast_time = datetime.utcfromtimestamp(item['dt']).replace(tzinfo=pytz.UTC)
            if start_date <= forecast_time.date() <= end_date:
                day = forecast_time.date().isoformat()
                if day not in daily_forecasts:
                    daily_forecasts[day] = []
                daily_forecasts[day].append(item)
        if not daily_forecasts:
            return error_response(f"No forecast available from {start_date.strftime('%Y-%m-%d')}")
        response_text = f"Weather forecast for {city} starting {start_date.strftime('%A, %B %d')}:\n\n"
        payload = {}
        for day, forecasts in daily_forecasts.items():
            temps = [f['main']['temp'] for f in forecasts]
            conditions = [f['weather'][0]['description'] for f in forecasts]
            common_condition = Counter(conditions).most_common(1)[0][0]
            response_text += (
                f"{datetime.strptime(day, '%Y-%m-%d').strftime('%A, %b %d')}:\n"
                f"• Condition: {common_condition.capitalize()}\n"
                f"• High: {max(temps):.1f}°C\n"
                f"• Low: {min(temps):.1f}°C\n\n"
            )
            payload[day] = {
                "condition": common_condition,
                "high_temp": max(temps),
                "low_temp": min(temps),
                "avg_temp": sum(temps) / len(temps)
            }
        return jsonify({
            "fulfillmentText": response_text.strip(),
            "payload": {
                "city": city,
                "forecast": payload
            }
        })
    except Exception as e:
        return error_response(f"Error processing forecast: {str(e)}")

def error_response(message):
    return jsonify({
        "fulfillmentText": message,
        "payload": {
            "error": True,
            "message": message
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)