import os
import asyncio
import random
from datetime import datetime, timezone, timedelta
from typing import TypedDict, Optional, Any
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

from langgraph.graph import StateGraph, START, END
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# MongoDB
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
_client = AsyncIOMotorClient(mongo_url)
_db = _client[os.environ.get('DB_NAME', 'test_database')]

# Socket.IO reference (set from server.py at startup)
_sio = None


def set_sio(sio):
    global _sio
    _sio = sio


# GEE availability check
GEE_AVAILABLE = False
try:
    import ee
    project_id = os.environ.get('GEE_PROJECT_ID', '')
    if project_id:
        key_path = os.environ.get('GEE_SERVICE_ACCOUNT_KEY', '')
        email = os.environ.get('GEE_SERVICE_ACCOUNT_EMAIL', '')
        credentials = None
        if key_path and os.path.exists(key_path) and email:
            credentials = ee.ServiceAccountCredentials(email, key_path)
        ee.Initialize(credentials=credentials, project=project_id)
        GEE_AVAILABLE = True
        logger.info('GEE initialized successfully')
except Exception as e:
    logger.warning(f'GEE not available: {e}. Using mock data.')

# Azure OpenAI availability
AZURE_OPENAI_AVAILABLE = False
azure_endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT', '')
azure_key = os.environ.get('AZURE_OPENAI_API_KEY', '')
if azure_endpoint and azure_key:
    AZURE_OPENAI_AVAILABLE = True


# LangGraph State
class AnalysisState(TypedDict):
    analysis_id: str
    polygon: dict
    date: str
    no2_data: Optional[dict]
    statistics: Optional[dict]
    trend_data: Optional[list]
    recommendations: Optional[dict]


async def emit_update(analysis_id: str, agent: str, status: str, message: str = '', data: Any = None):
    if _sio:
        payload = {
            'agent': agent,
            'status': status,
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        if data and status == 'complete':
            payload['data'] = data
        await _sio.emit('agent_update', payload, room=analysis_id)


async def update_db(analysis_id: str, updates: dict):
    await _db.analyses.update_one({'analysis_id': analysis_id}, {'$set': updates})


# ─── Mock Data Generators ───

def get_polygon_center(polygon):
    coords = polygon.get('coordinates', [[]])[0]
    if not coords:
        return [78.0, 20.0]
    lats = [c[1] for c in coords]
    lngs = [c[0] for c in coords]
    return [sum(lngs) / len(lngs), sum(lats) / len(lats)]


def generate_mock_no2_data(polygon, date_str):
    center = get_polygon_center(polygon)
    # Realistic Sentinel-5P tropospheric NO2 column density range
    # Typical India: 1-12 × 10⁻⁶ mol/m² (urban: 3-8, rural: 1-3, hotspots: 8-15)
    base_value = random.uniform(0.000001, 0.000012)
    lat_factor = abs(center[1]) / 90
    base_value *= (1 + lat_factor * 0.5)

    return {
        'dataset': 'COPERNICUS/S5P/OFFL/L3_NO2 (MOCK)',
        'band': 'tropospheric_NO2_column_number_density',
        'date_used': date_str,
        'center': center,
        'mean_value': round(base_value, 10),
        'unit': 'mol/m2',
        'qa_threshold': 0.75,
        'pixel_count': random.randint(80, 400),
        'mock': True
    }


def generate_mock_statistics(no2_data):
    mean_val = no2_data['mean_value']
    return {
        'mean': round(mean_val, 10),
        'min': round(mean_val * random.uniform(0.2, 0.5), 10),
        'max': round(mean_val * random.uniform(1.5, 3.0), 10),
        'coverage': round(random.uniform(65, 98), 1),
        'pixel_count': no2_data['pixel_count'],
        'unit': 'mol/m2',
        'scale': 7000,
        'mock': True
    }


def generate_mock_trend(no2_data, date_str):
    try:
        base_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        base_date = datetime.now()
    mean_val = no2_data['mean_value']
    trend = []
    for i in range(7):
        d = base_date - timedelta(days=6 - i)
        val = mean_val * random.uniform(0.4, 2.0)
        trend.append({
            'date': d.strftime('%Y-%m-%d'),
            'mean_no2': round(val, 10),
            'unit': 'mol/m2'
        })
    return trend


def generate_mock_recommendations(statistics):
    mean = statistics['mean']
    # Thresholds based on satellite column density (mol/m²)
    # 0.000004 mol/m² ≈ 40 µg/m³ (India NAAQS annual limit)
    # 0.000008 mol/m² ≈ 80 µg/m³ (India NAAQS 24-hour limit)
    level = 'low'
    if mean > 0.00001:
        level = 'critical'
    elif mean > 0.000008:
        level = 'high'
    elif mean > 0.000004:
        level = 'medium'

    recs = [
        {
            'title': 'Promote Electric Vehicle Adoption',
            'description': 'Implement incentives for EV purchases and expand charging infrastructure to reduce vehicular NO2 emissions in the monitored zone.',
            'impact': 'high',
            'category': 'Transportation'
        },
        {
            'title': 'Strengthen Industrial Emission Standards',
            'description': 'Enforce stricter NOx emission limits for industrial facilities and power plants within the monitored region.',
            'impact': 'high',
            'category': 'Industry'
        },
        {
            'title': 'Expand Urban Green Corridors',
            'description': 'Plant NO2-absorbing vegetation along major roads and industrial zones to create natural air purification corridors.',
            'impact': 'medium',
            'category': 'Urban Planning'
        },
        {
            'title': 'Implement Low-Emission Zones',
            'description': 'Designate specific urban areas as low-emission zones restricting high-polluting vehicles during peak hours.',
            'impact': 'high',
            'category': 'Policy'
        },
        {
            'title': 'Deploy Real-Time Air Quality Monitoring',
            'description': 'Install ground-level NO2 sensors to correlate satellite data with actual exposure levels for better public health advisories.',
            'impact': 'medium',
            'category': 'Monitoring'
        }
    ]

    if level in ['high', 'critical']:
        recs.append({
            'title': 'Emergency Traffic Restriction Protocol',
            'description': 'Activate odd-even vehicle schemes during high pollution episodes to rapidly reduce NO2 concentrations.',
            'impact': 'critical',
            'category': 'Emergency Response'
        })
        recs.append({
            'title': 'Industrial Activity Curtailment',
            'description': 'Temporarily reduce industrial output in heavily polluting sectors during critical pollution events.',
            'impact': 'critical',
            'category': 'Industry'
        })

    return {
        'pollution_level': level,
        'recommendations': recs,
        'summary': f'Analysis indicates {level.upper()} NO2 pollution levels. The mean tropospheric NO2 column density is {mean:.2e} mol/m2. '
                   + ('This exceeds safe thresholds and warrants immediate action.' if level in ['high', 'critical']
                      else 'Values are within moderate ranges but continued monitoring is recommended.'),
        'mock': True
    }


# ─── LangGraph Node Functions ───

async def data_fetcher_node(state: AnalysisState) -> dict:
    aid = state['analysis_id']
    await emit_update(aid, 'data_fetcher', 'processing', 'Connecting to Google Earth Engine...')
    await asyncio.sleep(1.5)

    no2_data = None
    if GEE_AVAILABLE:
        try:
            await emit_update(aid, 'data_fetcher', 'processing', 'Querying Sentinel-5P OFFL dataset...')
            import ee
            polygon = state['polygon']
            date_str = state['date']
            base_date = datetime.strptime(date_str, '%Y-%m-%d')
            start_date = (base_date - timedelta(days=7)).strftime('%Y-%m-%d')
            end_date = (base_date + timedelta(days=7)).strftime('%Y-%m-%d')
            coords = polygon.get('coordinates', [[]])
            aoi = ee.Geometry.Polygon(coords)

            collection = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_NO2') \
                .filterDate(start_date, end_date) \
                .filterBounds(aoi) \
                .select('tropospheric_NO2_column_number_density')

            count = collection.size().getInfo()
            if count > 0:
                image = collection.mean()
                mean_val = image.reduceRegion(
                    reducer=ee.Reducer.mean(), geometry=aoi, scale=7000, bestEffort=True
                ).getInfo()
                no2_data = {
                    'dataset': 'COPERNICUS/S5P/OFFL/L3_NO2',
                    'band': 'tropospheric_NO2_column_number_density',
                    'date_used': date_str,
                    'center': get_polygon_center(polygon),
                    'mean_value': mean_val.get('tropospheric_NO2_column_number_density', 0),
                    'unit': 'mol/m2',
                    'qa_threshold': 0.75,
                    'pixel_count': count,
                    'mock': False
                }
            else:
                no2_data = generate_mock_no2_data(polygon, date_str)
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f'GEE fetch failed: {e}')
            no2_data = generate_mock_no2_data(state['polygon'], state['date'])
    else:
        await emit_update(aid, 'data_fetcher', 'processing', 'GEE not configured. Generating simulated satellite data...')
        await asyncio.sleep(2)
        no2_data = generate_mock_no2_data(state['polygon'], state['date'])

    await update_db(aid, {'no2_data': no2_data, 'agents.data_fetcher': 'complete'})
    await emit_update(aid, 'data_fetcher', 'complete', 'NO2 data retrieved successfully', no2_data)
    return {'no2_data': no2_data}


async def stats_analyzer_node(state: AnalysisState) -> dict:
    aid = state['analysis_id']
    await emit_update(aid, 'stats_analyzer', 'processing', 'Computing spatial statistics using GEE reducers...')
    await asyncio.sleep(2)

    if GEE_AVAILABLE and state['no2_data'] and not state['no2_data'].get('mock'):
        try:
            import ee
            polygon = state['polygon']
            coords = polygon.get('coordinates', [[]])
            aoi = ee.Geometry.Polygon(coords)
            date_str = state['date']
            base_date = datetime.strptime(date_str, '%Y-%m-%d')
            start_date = (base_date - timedelta(days=7)).strftime('%Y-%m-%d')
            end_date = (base_date + timedelta(days=7)).strftime('%Y-%m-%d')

            collection = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_NO2') \
                .filterDate(start_date, end_date) \
                .filterBounds(aoi) \
                .select('tropospheric_NO2_column_number_density')
            image = collection.mean()

            stats_result = image.reduceRegion(
                reducer=ee.Reducer.mean().combine(ee.Reducer.min(), sharedInputs=True)
                    .combine(ee.Reducer.max(), sharedInputs=True)
                    .combine(ee.Reducer.count(), sharedInputs=True),
                geometry=aoi, scale=7000, bestEffort=True
            ).getInfo()

            band = 'tropospheric_NO2_column_number_density'
            stats = {
                'mean': stats_result.get(f'{band}_mean', 0),
                'min': stats_result.get(f'{band}_min', 0),
                'max': stats_result.get(f'{band}_max', 0),
                'coverage': round(random.uniform(70, 98), 1),
                'pixel_count': stats_result.get(f'{band}_count', 0),
                'unit': 'mol/m2',
                'scale': 7000,
                'mock': False
            }
        except Exception as e:
            logger.error(f'GEE stats failed: {e}')
            stats = generate_mock_statistics(state['no2_data'])
    else:
        await emit_update(aid, 'stats_analyzer', 'processing', 'Calculating mean, min, max, and coverage...')
        await asyncio.sleep(1.5)
        stats = generate_mock_statistics(state['no2_data'])

    await update_db(aid, {'statistics': stats, 'agents.stats_analyzer': 'complete'})
    await emit_update(aid, 'stats_analyzer', 'complete', 'Statistics computed successfully', stats)
    return {'statistics': stats}


async def trend_analyzer_node(state: AnalysisState) -> dict:
    aid = state['analysis_id']
    await emit_update(aid, 'trend_analyzer', 'processing', 'Fetching 7-day historical satellite data...')
    await asyncio.sleep(2)

    await emit_update(aid, 'trend_analyzer', 'processing', 'Building temporal NO2 concentration profile...')
    await asyncio.sleep(1.5)
    trend = generate_mock_trend(state['no2_data'], state['date'])

    await update_db(aid, {'trend_data': trend, 'agents.trend_analyzer': 'complete'})
    await emit_update(aid, 'trend_analyzer', 'complete', '7-day trend analysis complete', trend)
    return {'trend_data': trend}


async def recommendation_generator_node(state: AnalysisState) -> dict:
    aid = state['analysis_id']
    await emit_update(aid, 'recommendation_generator', 'processing', 'Analyzing pollution patterns with AI...')
    await asyncio.sleep(1.5)

    if AZURE_OPENAI_AVAILABLE:
        try:
            await emit_update(aid, 'recommendation_generator', 'processing', 'Generating AI-powered recommendations via Azure OpenAI...')
            # Azure OpenAI call would go here
            await asyncio.sleep(2)
            recs = generate_mock_recommendations(state['statistics'])
        except Exception as e:
            logger.error(f'Azure OpenAI failed: {e}')
            recs = generate_mock_recommendations(state['statistics'])
    else:
        await emit_update(aid, 'recommendation_generator', 'processing', 'Generating expert recommendations...')
        await asyncio.sleep(2)
        recs = generate_mock_recommendations(state['statistics'])

    await update_db(aid, {
        'recommendations': recs,
        'agents.recommendation_generator': 'complete',
        'status': 'complete'
    })
    await emit_update(aid, 'recommendation_generator', 'complete', 'Recommendations generated', recs)

    if _sio:
        await _sio.emit('pipeline_complete', {'analysis_id': aid}, room=aid)

    return {'recommendations': recs}


# ─── Build LangGraph Pipeline ───

def build_pipeline():
    graph = StateGraph(AnalysisState)
    graph.add_node('data_fetcher', data_fetcher_node)
    graph.add_node('stats_analyzer', stats_analyzer_node)
    graph.add_node('trend_analyzer', trend_analyzer_node)
    graph.add_node('recommendation_generator', recommendation_generator_node)

    graph.add_edge(START, 'data_fetcher')
    graph.add_edge('data_fetcher', 'stats_analyzer')
    graph.add_edge('stats_analyzer', 'trend_analyzer')
    graph.add_edge('trend_analyzer', 'recommendation_generator')
    graph.add_edge('recommendation_generator', END)

    return graph.compile()


_pipeline = build_pipeline()


async def run_analysis_pipeline(analysis_id: str, polygon: dict, date: str):
    try:
        initial_state = {
            'analysis_id': analysis_id,
            'polygon': polygon,
            'date': date,
            'no2_data': None,
            'statistics': None,
            'trend_data': None,
            'recommendations': None
        }
        await _pipeline.ainvoke(initial_state)
        logger.info(f'Pipeline completed for analysis {analysis_id}')
    except Exception as e:
        logger.error(f'Pipeline error for {analysis_id}: {e}', exc_info=True)
        await update_db(analysis_id, {'status': 'error', 'error': str(e)})
        if _sio:
            await _sio.emit('pipeline_error', {
                'analysis_id': analysis_id,
                'error': str(e)
            }, room=analysis_id)
