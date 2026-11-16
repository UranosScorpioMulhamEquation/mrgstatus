import datetime
import os
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional

import geonamescache
import pytz
import streamlit as st
import swisseph as swe
from timezonefinder import TimezoneFinder

# =============================================================================
# 1. إعدادات المحرك الفلكي (Swiss Ephemeris) وتنسيق واجهة Streamlit (RTL)
# =============================================================================
EPHE_PATH = "./ephe"
if not os.path.exists(EPHE_PATH):
    os.makedirs(EPHE_PATH)

swe.set_ephe_path(EPHE_PATH)

st.set_page_config(
    page_title="المحرك الفلكي المتقدم لتقييم قوى الكواكب وصلاحية الزواج",
    layout="wide",
    page_icon="🔭"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&family=Amiri:wght@700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: rtl;
        text-align: right;
    }
    
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
        color: #ffffff;
        font-weight: 800;
        font-size: 17px;
        padding: 14px;
        border-radius: 10px;
        border: 1px solid #d4af37;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #d4af37 0%, #b48a1e 100%);
        color: #0f172a;
        border-color: #fde047;
        box-shadow: 0 4px 18px rgba(212, 175, 55, 0.45);
    }
    .main-header {
        text-align: center;
        background: linear-gradient(135deg, #090d16 0%, #172554 100%);
        color: #f8fafc;
        padding: 26px;
        border-radius: 14px;
        border: 2px solid #d4af37;
        margin-bottom: 25px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.12);
    }
    .main-header h1 {
        font-family: 'Amiri', serif;
        color: #facc15;
        font-size: 30px;
        margin-bottom: 8px;
        font-weight: 700;
    }
    .result-card {
        background: #ffffff;
        border-right: 6px solid #d4af37;
        border-radius: 10px;
        padding: 22px;
        margin-bottom: 20px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.06);
        border: 1px solid #e2e8f0;
    }
    .rec-box {
        background: #f8fafc;
        border-right: 5px solid #2563eb;
        padding: 18px;
        border-radius: 10px;
        margin-top: 15px;
        border: 1px solid #cbd5e1;
    }
    .planet-detail-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. وحدة البيانات الجغرافية والمناطق الزمنية الديناميكية
# =============================================================================
@dataclass
class City:
    geonameid: str
    name: str
    country_code: str
    latitude: float
    longitude: float
    admin1: str
    population: int

@st.cache_data
def load_geo_data():
    gc = geonamescache.GeonamesCache()
    countries = gc.get_countries()
    raw_cities = gc.get_cities()

    country_map = {c["name"]: code for code, c in countries.items()}
    sorted_countries = sorted(list(country_map.keys()))

    cities_by_country: Dict[str, List[City]] = {code: [] for code in country_map.values()}
    for city_id, c_data in raw_cities.items():
        if c_data.get("population", 0) >= 15000:
            c_code = c_data.get("countrycode", "")
            if c_code in cities_by_country:
                cities_by_country[c_code].append(
                    City(
                        geonameid=city_id,
                        name=c_data.get("name", ""),
                        country_code=c_code,
                        latitude=float(c_data.get("latitude", 0.0)),
                        longitude=float(c_data.get("longitude", 0.0)),
                        admin1=c_data.get("admin1code", ""),
                        population=int(c_data.get("population", 0)),
                    )
                )

    for c_code in cities_by_country:
        cities_by_country[c_code].sort(key=lambda x: x.population, reverse=True)

    return country_map, sorted_countries, cities_by_country

country_map, country_list, cities_by_country = load_geo_data()
tf = TimezoneFinder()

# =============================================================================
# 3. المعاجم الفلكية الشاملة (الكواكب العشرة، الكرامات، الكويكبات، والنجوم الثابتة)
# =============================================================================
ZODIAC_NAMES_AR = [
    "الحمل", "الثور", "الجوزاء", "السرطان",
    "الأسد", "العذراء", "الميزان", "العقرب",
    "القوس", "الجدي", "الدلو", "الحوت"
]

PERSONAL_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars"]

ALL_PLANETS_IDS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO
}

ALL_PLANETS_AR = {
    "Sun": "الشمس",
    "Moon": "القمر",
    "Mercury": "عطارد",
    "Venus": "الزهرة",
    "Mars": "المريخ",
    "Jupiter": "المشتري",
    "Saturn": "زحل",
    "Uranus": "أورانوس",
    "Neptune": "نبتون",
    "Pluto": "بلوتو"
}

AVERAGE_DAILY_SPEEDS = {
    "Sun": 0.9856,
    "Moon": 13.1764,
    "Mercury": 1.383,
    "Venus": 1.200,
    "Mars": 0.524
}

SIGN_RULERS = {
    0: "Mars", 1: "Venus", 2: "Mercury", 3: "Moon",
    4: "Sun", 5: "Mercury", 6: "Venus", 7: "Mars",
    8: "Jupiter", 9: "Saturn", 10: "Saturn", 11: "Jupiter"
}

EXALTATIONS = {
    "Sun": (0, 19.0),
    "Moon": (1, 3.0),
    "Mercury": (5, 15.0),
    "Venus": (11, 27.0),
    "Mars": (9, 28.0)
}

DETRIMENTS = {
    "Sun": [10],
    "Moon": [9],
    "Mercury": [8, 11],
    "Venus": [0, 7],
    "Mars": [1, 6]
}

FALLS = {
    "Sun": 6,
    "Moon": 7,
    "Mercury": 11,
    "Venus": 5,
    "Mars": 3
}

TRIPLICITY_RULERS = {
    0: ("Sun", "Jupiter", "Saturn"),
    1: ("Venus", "Moon", "Mars"),
    2: ("Saturn", "Mercury", "Jupiter"),
    3: ("Venus", "Mars", "Moon")
}

EGYPTIAN_TERMS = {
    0: [(6, "Jupiter"), (12, "Venus"), (20, "Mercury"), (25, "Mars"), (30, "Saturn")],
    1: [(8, "Venus"), (14, "Mercury"), (22, "Jupiter"), (27, "Saturn"), (30, "Mars")],
    2: [(6, "Mercury"), (12, "Jupiter"), (17, "Venus"), (24, "Mars"), (30, "Saturn")],
    3: [(7, "Mars"), (13, "Venus"), (19, "Mercury"), (26, "Jupiter"), (30, "Saturn")],
    4: [(6, "Jupiter"), (11, "Venus"), (18, "Saturn"), (24, "Mercury"), (30, "Mars")],
    5: [(7, "Mercury"), (17, "Venus"), (21, "Jupiter"), (28, "Mars"), (30, "Saturn")],
    6: [(6, "Saturn"), (14, "Mercury"), (21, "Jupiter"), (28, "Venus"), (30, "Mars")],
    7: [(7, "Mars"), (11, "Venus"), (19, "Mercury"), (24, "Jupiter"), (30, "Saturn")],
    8: [(12, "Jupiter"), (17, "Venus"), (21, "Mercury"), (26, "Saturn"), (30, "Mars")],
    9: [(7, "Mercury"), (14, "Jupiter"), (22, "Venus"), (26, "Saturn"), (30, "Mars")],
    10: [(7, "Mercury"), (13, "Venus"), (20, "Jupiter"), (25, "Mars"), (30, "Saturn")],
    11: [(12, "Venus"), (16, "Jupiter"), (19, "Mercury"), (28, "Mars"), (30, "Saturn")]
}

CHALDEAN_ORDER = ["Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter"]

ASTEROIDS_IDS = {
    "Chiron": swe.CHIRON,
    "Ceres": swe.CERES,
    "Pallas": swe.PALLAS,
    "Juno": swe.JUNO,
    "Vesta": swe.VESTA
}

ASTEROIDS_AR = {
    "Chiron": "كيرون (المعالج)",
    "Ceres": "سيريس (الأمومة والغذاء)",
    "Pallas": "بالاس (الحكمة)",
    "Juno": "جونو (عقد الزواج والشراكة)",
    "Vesta": "فيستا (الالتزام والبيت)"
}

# كتالوج النجوم الثابتة الفعلي المتوافق مع Swiss Ephemeris
FIXED_STARS_CATALOG = [
    ("Regulus", "قلب الأسد (Regulus)", +5.0, "نجم ملكي: مجد وقيادة ورفعة"),
    ("Spica", "السماك الأعزل (Spica)", +5.5, "أعظم نجوم الحظ والمواهب والحماية"),
    ("Aldebaran", "الدبران (Aldebaran)", +3.5, "نجم ملكي: نجاح وشجاعة بشرط النزاهة"),
    ("Antares", "قلب العقرب (Antares)", +2.5, "نجم ملكي: قوة عاطفية وحسم"),
    ("Fomalhaut", "فم الحوت (Fomalhaut)", +3.5, "نجم ملكي: مثالية وتألق روحي"),
    ("Sirius", "الشعرى اليمانية (Sirius)", +4.5, "تألق وشهرة ونجاح استثنائي"),
    ("Vega", "النسر الواقع (Vega)", +3.0, "جاذبية فنية وكاريزما وسحر"),
    ("Arcturus", "السماك الرامح (Arcturus)", +3.5, "ريادة وعدالة وثروة"),
    ("Algol", "رأس الغول (Algol)", -5.5, "نجم عنيف: حدة وتوتر شديد"),
    ("Alcyone", "الثريا (Alcyone)", -2.5, "حساسية عاطفية وتقلبات")
]

# =============================================================================
# 4. دوال الحسابات الفلكية الهندسية والدقيقة
# =============================================================================
def angular_diff(lon1: float, lon2: float) -> float:
    diff = abs(lon1 - lon2) % 360.0
    return min(diff, 360.0 - diff)

def get_aspect_details(lon1: float, lon2: float) -> Optional[Tuple[str, float, float]]:
    dist = angular_diff(lon1, lon2)
    aspects_rules = [
        ("اقتران (0°)", 0.0, 8.0),
        ("مقابلة (180°)", 180.0, 8.0),
        ("تثليث (120°)", 120.0, 7.0),
        ("تربيع (90°)", 90.0, 7.0),
        ("تسديس (60°)", 60.0, 5.0),
    ]
    for asp_name, target_angle, max_orb in aspects_rules:
        orb = abs(dist - target_angle)
        if orb <= max_orb:
            precision_factor = 1.0 - (orb / max_orb) * 0.4
            return asp_name, orb, precision_factor
    return None

def get_term_ruler(sign_idx: int, deg_in_sign: float) -> str:
    for limit, ruler in EGYPTIAN_TERMS[sign_idx]:
        if deg_in_sign < limit:
            return ruler
    return EGYPTIAN_TERMS[sign_idx][-1][1]

def get_face_ruler(sign_idx: int, deg_in_sign: float) -> str:
    decan_idx = min(2, int(deg_in_sign // 10))
    total_decan = sign_idx * 3 + decan_idx
    return CHALDEAN_ORDER[total_decan % 7]

def compute_fixed_stars(jd: float) -> List[Dict[str, Any]]:
    """حساب المواقع الحقيقية والدقيقة للنجوم الثابتة عبر محرك سويس إيفيميريس."""
    stars_positions = []
    for star_key, star_ar, weight, desc in FIXED_STARS_CATALOG:
        try:
            res, _ = swe.fixstar2_ut(star_key, jd)
            stars_positions.append({
                "key": star_key,
                "name_ar": star_ar,
                "lon": res[0],
                "weight": weight,
                "desc": desc
            })
        except Exception:
            continue
    return stars_positions

# =============================================================================
# 5. محرك تقييم قوى الكواكب الشخصية (مقياس 100 نقطة)
# =============================================================================
def evaluate_planet_100_scale(
    planet_name: str,
    all_planets: Dict[str, Dict[str, Any]],
    asteroids: Dict[str, Dict[str, Any]],
    fixed_stars: List[Dict[str, Any]],
    is_day_chart: bool,
    has_birth_time: bool
) -> Tuple[float, List[str], Dict[str, float]]:
    p_data = all_planets[planet_name]
    p_lon = p_data["lon"]
    p_speed = p_data["speed"]
    sign_idx = p_data["sign_idx"]
    deg_in_sign = p_data["deg_in_sign"]
    house_num = p_data["whole_sign_house"]

    score = 40.0  # القيمة الأساسية المحايدة (Baseline)
    breakdown = {
        "essential": 0.0,
        "accidental": 0.0,
        "planets_aspects": 0.0,
        "asteroids_stars": 0.0
    }
    reasons: List[str] = ["نقطة الأساس المحايدة: 40.0"]
    has_any_essential_dignity = False

    # أ) الكرامات الذاتية
    if SIGN_RULERS.get(sign_idx) == planet_name:
        score += 12.0
        breakdown["essential"] += 12.0
        has_any_essential_dignity = True
        reasons.append("في بيته [+12.0]")

    exalt_info = EXALTATIONS.get(planet_name)
    if exalt_info and exalt_info[0] == sign_idx:
        score += 15.0
        breakdown["essential"] += 15.0
        has_any_essential_dignity = True
        reasons.append("في شرفه [+15.0]")
        if abs(deg_in_sign - exalt_info[1]) <= 1.5:
            score += 3.0
            breakdown["essential"] += 3.0
            reasons.append("في درجة الشرف الدقيقة [+3.0]")

    element_idx = sign_idx % 4
    day_ruler, night_ruler, part_ruler = TRIPLICITY_RULERS[element_idx]
    primary_trip = day_ruler if is_day_chart else night_ruler
    if planet_name == primary_trip:
        score += 7.0
        breakdown["essential"] += 7.0
        has_any_essential_dignity = True
        reasons.append("رب المثلثة [+7.0]")
    elif planet_name == part_ruler:
        score += 4.0
        breakdown["essential"] += 4.0
        has_any_essential_dignity = True
        reasons.append("شريك المثلثة [+4.0]")

    if get_term_ruler(sign_idx, deg_in_sign) == planet_name:
        score += 5.0
        breakdown["essential"] += 5.0
        has_any_essential_dignity = True
        reasons.append("في حده المصري [+5.0]")

    if get_face_ruler(sign_idx, deg_in_sign) == planet_name:
        score += 3.0
        breakdown["essential"] += 3.0
        has_any_essential_dignity = True
        reasons.append("في وجهه [+3.0]")

    # ب) الانتكاسات
    is_detriment = sign_idx in DETRIMENTS.get(planet_name, [])
    is_fall = (FALLS.get(planet_name) == sign_idx)

    if is_detriment and is_fall:
        score -= 18.0
        breakdown["essential"] -= 18.0
        reasons.append("في وباله وهبوطه معاً [-18.0]")
    else:
        if is_detriment:
            score -= 12.0
            breakdown["essential"] -= 12.0
            reasons.append("في وباله [-12.0]")
        if is_fall:
            score -= 15.0
            breakdown["essential"] -= 15.0
            reasons.append("في هبوطه [-15.0]")

    if not has_any_essential_dignity and not is_detriment and not is_fall:
        score -= 5.0
        breakdown["essential"] -= 5.0
        reasons.append("غريب بلا حظ ذاتي [-5.0]")

    # ج) التبادل بالربوبية
    host_ruler = SIGN_RULERS.get(sign_idx)
    if host_ruler and host_ruler != planet_name and host_ruler in all_planets:
        host_sign = all_planets[host_ruler]["sign_idx"]
        if SIGN_RULERS.get(host_sign) == planet_name:
            score += 10.0
            breakdown["essential"] += 10.0
            reasons.append(f"تبادل كامل بالبيت مع {ALL_PLANETS_AR[host_ruler]} [+10.0]")
        elif EXALTATIONS.get(planet_name) and EXALTATIONS[planet_name][0] == host_sign:
            score += 7.0
            breakdown["essential"] += 7.0
            reasons.append(f"تبادل مختلط مع {ALL_PLANETS_AR[host_ruler]} [+7.0]")

    # د) الكرامات العرضية والبيوت
    if has_birth_time:
        if house_num in [1, 10]:
            score += 10.0
            breakdown["accidental"] += 10.0
            reasons.append(f"في وتد رئيسي (بيت {house_num}) [+10.0]")
        elif house_num in [4, 7]:
            score += 8.0
            breakdown["accidental"] += 8.0
            reasons.append(f"في وتد (بيت {house_num}) [+8.0]")
        elif house_num in [5, 11]:
            score += 6.0
            breakdown["accidental"] += 6.0
            reasons.append(f"في بيت سعيد (بيت {house_num}) [+6.0]")
        elif house_num in [2, 9]:
            score += 4.0
            breakdown["accidental"] += 4.0
            reasons.append(f"في بيت داعم (بيت {house_num}) [+4.0]")
        elif house_num == 3:
            score += 1.0
            breakdown["accidental"] += 1.0
            reasons.append("في فرح القمر (بيت 3) [+1.0]")
        elif house_num in [6, 8, 12]:
            score -= 7.0
            breakdown["accidental"] -= 7.0
            reasons.append(f"في بيت ساقط (بيت {house_num}) [-7.0]")

    avg_spd = AVERAGE_DAILY_SPEEDS[planet_name]
    if planet_name not in ["Sun", "Moon"]:
        if p_speed < 0:
            score -= 8.0
            breakdown["accidental"] -= 8.0
            reasons.append(f"متراجع (R: {p_speed:.2f}°) [-8.0]")
        elif abs(p_speed) < 0.08:
            score -= 4.0
            breakdown["accidental"] -= 4.0
            reasons.append("متوقف (Stationary) [-4.0]")
        else:
            if p_speed > avg_spd * 1.15:
                score += 4.0
                breakdown["accidental"] += 4.0
                reasons.append("سريع الحركة [+4.0]")
            else:
                score += 2.0
                breakdown["accidental"] += 2.0
                reasons.append("مستقيم الحركة [+2.0]")
    else:
        if p_speed > avg_spd * 1.05:
            score += 3.0
            breakdown["accidental"] += 3.0
            reasons.append("سريع السير [+3.0]")

    if planet_name != "Sun":
        sun_dist = angular_diff(p_lon, all_planets["Sun"]["lon"])
        if sun_dist <= 0.2833:
            score += 12.0
            breakdown["accidental"] += 12.0
            reasons.append("في صميم الشمس (Cazimi) [+12.0]")
        elif sun_dist <= 8.5:
            combust_pen = -5.0 if (SIGN_RULERS.get(sign_idx) == planet_name or (exalt_info and exalt_info[0] == sign_idx)) else -10.0
            score += combust_pen
            breakdown["accidental"] += combust_pen
            reasons.append(f"محترق بالشمس ({sun_dist:.1f}°) [{combust_pen}]")
        elif sun_dist <= 17.0:
            score -= 5.0
            breakdown["accidental"] -= 5.0
            reasons.append(f"تحت شعاع الشمس ({sun_dist:.1f}°) [-5.0]")

    diurnal_planets = ["Sun", "Jupiter", "Saturn"]
    nocturnal_planets = ["Moon", "Venus", "Mars"]
    if (is_day_chart and planet_name in diurnal_planets) or (not is_day_chart and planet_name in nocturnal_planets):
        score += 3.0
        breakdown["accidental"] += 3.0
        reasons.append("موافق للحيّز [+3.0]")

    # هـ) اتصالات الكواكب العشرة
    benefics = ["Jupiter", "Venus"]
    malefics = ["Saturn", "Mars"]
    outers_hard = ["Uranus", "Neptune", "Pluto"]

    for other_p, other_info in all_planets.items():
        if other_p == planet_name:
            continue
        asp_res = get_aspect_details(p_lon, other_info["lon"])
        if not asp_res:
            continue

        asp_name, orb, prec = asp_res
        other_ar = ALL_PLANETS_AR[other_p]
        delta = 0.0

        if asp_name in ["تثليث (120°)", "تسديس (60°)"]:
            base_w = 5.5 if other_p in benefics else (4.0 if other_p in ["Sun", "Moon", "Mercury"] else 3.0)
            delta = round(base_w * prec, 1)
        elif asp_name == "اقتران (0°)":
            if other_p in benefics:
                delta = round(6.5 * prec, 1)
            elif other_p in malefics:
                delta = round(-6.5 * prec, 1)
            elif other_p in outers_hard:
                delta = round(-4.5 * prec, 1)
            else:
                delta = round(4.0 * prec, 1)
        elif asp_name in ["تربيع (90°)", "مقابلة (180°)"]:
            if other_p in malefics:
                delta = round(-6.5 * prec, 1)
            elif other_p in outers_hard:
                delta = round(-5.0 * prec, 1)
            elif other_p in benefics:
                delta = round(-2.0 * prec, 1)
            else:
                delta = round(-3.5 * prec, 1)

        if delta != 0.0:
            score += delta
            breakdown["planets_aspects"] += delta
            sign_str = "+" if delta > 0 else ""
            reasons.append(f"{asp_name} مع {other_ar} (أورب {orb:.1f}°) [{sign_str}{delta}]")

    # و) اتصالات الكويكبات
    for ast_name, ast_info in asteroids.items():
        dist = angular_diff(p_lon, ast_info["lon"])
        ast_ar = ASTEROIDS_AR[ast_name]
        delta = 0.0
        if dist <= 3.0:
            if ast_name in ["Juno", "Ceres", "Vesta", "Pallas"]:
                delta = 2.5
                reasons.append(f"اقتران مع كويكب {ast_ar} [+2.5]")
            elif ast_name == "Chiron":
                delta = -2.5
                reasons.append(f"اقتران مع كويكب {ast_ar} [-2.5]")
        elif abs(dist - 120.0) <= 2.5 or abs(dist - 60.0) <= 2.5:
            delta = 1.5
            reasons.append(f"اتصال سعيد مع {ast_ar} [+1.5]")
        elif abs(dist - 90.0) <= 2.5 or abs(dist - 180.0) <= 2.5:
            delta = -1.5
            reasons.append(f"اتصال ضاغط مع {ast_ar} [-1.5]")

        if delta != 0.0:
            score += delta
            breakdown["asteroids_stars"] += delta

    # ز) اقترانات ومقابلات النجوم الثابتة الحقيقية
    for star in fixed_stars:
        dist = angular_diff(p_lon, star["lon"])
        if dist <= 1.5:
            w = star["weight"]
            score += w
            breakdown["asteroids_stars"] += w
            sign_str = "+" if w > 0 else ""
            reasons.append(f"اقتران بالنجم الثابت {star['name_ar']} ({star['desc']}) [{sign_str}{w}]")
        elif abs(dist - 180.0) <= 1.2 and star["weight"] < 0:
            w = round(star["weight"] * 0.6, 1)
            score += w
            breakdown["asteroids_stars"] += w
            reasons.append(f"مقابلة النجم الثابت {star['name_ar']} [{w}]")

    final_score = round(min(100.0, score), 1)
    return final_score, reasons, breakdown

def get_strength_classification(score: float) -> Tuple[str, str, str]:
    """
    تصنيف قوة الكوكب الدقيق وفق مقياس 100 نقطة:
    - أكثر من 60 (> 60): قوي
    - من 50 إلى 60 (50 <= score <= 60): متوسط القوى
    - أقل من 50 (< 50): ضعيف
    """
    if score > 60.0:
        return "قوي", "🟢", "strong"
    elif 50.0 <= score <= 60.0:
        return "متوسط القوى", "🟡", "moderate"
    else:
        return "ضعيف", "🔴", "weak"

# =============================================================================
# 6. دالة تقديم الحلول والعلاجات الفلكية المتقدمة
# =============================================================================
def get_advanced_recommendations(
    gender: str,
    venus_sc: float,
    moon_sc: float,
    sun_sc: float,
    mars_sc: float,
    fem_power: float,
    masc_power: float
) -> List[str]:
    recommendations = []
    is_venus_strong = venus_sc > 60.0
    is_moon_strong = moon_sc > 60.0
    is_sun_strong = sun_sc > 60.0
    is_mars_strong = mars_sc > 60.0
    
    if gender == "أنثى":
        if is_venus_strong and is_moon_strong and (fem_power > masc_power):
            recommendations.append("✨ **حالة متوازنة وممتازة:** طاقة الأنوثة والقمر والزهرة في أعلى مستويات التناغم.")
        else:
            if is_venus_strong and not is_moon_strong:
                recommendations.append("🏡 **دعم الجانب المنزلي والعاطفي (تقوية القمر فلكياً):** استخدام البابونج والأعشاب المهدئة وتنظيم شؤون المنزل.")
            if not is_venus_strong and is_moon_strong:
                recommendations.append("💖 **دعم جانب الثقافة الزوجية والعلاقة (تقوية الزهرة فلكياً):** الاهتمام بالجمال والعطور الفواحة والورد المحمدي.")
            if (not is_venus_strong and not is_moon_strong) or (fem_power <= masc_power):
                recommendations.append("🛠️ **برنامج متكامل لتعزيز طاقة الأنوثة والزهرة والقمر معاَ.**")
    else:
        if (masc_power > fem_power) and is_sun_strong and is_mars_strong:
            recommendations.append("👑 **حالة ذكورية قيادية متوازنة:** طاقة الشمس والمريخ تدعم القيادة وتحمل المسؤولية بكفاءة عالية.")
        else:
            if is_sun_strong and not is_mars_strong:
                recommendations.append("🛠️ **دعم الجانب البدني والمهاري المنزلي (تقوية المريخ فلكياً):** بالتمارين الرياضية وأعشاب الزنجبيل والقرفة.")
            if not is_sun_strong and is_mars_strong:
                recommendations.append("👔 **دعم الجانب القيادي والإداري الأسري (تقوية الشمس فلكياً):** بالتعرض لضوء الشمس الصباحي وإكليل الجبل.")
            if (not is_sun_strong and not is_mars_strong) or (masc_power <= fem_power):
                recommendations.append("🚀 **برنامج مكثف لتطوير المهارات القيادية والبدنية (الشمس والمريخ).**")
    return recommendations

# =============================================================================
# 7. مولد تقرير HTML الشامل والقابل للطباعة
# =============================================================================
def generate_html_report(data: Dict[str, Any]) -> str:
    planets_rows = ""
    for p_name in PERSONAL_PLANETS:
        p_info = data["all_planets"][p_name]
        sc = data["scores"][p_name]
        reasons_html = "".join([f"<span class='tag'>{r}</span>" for r in data["reasons"][p_name]])
        lbl, icon, status_cls = get_strength_classification(sc)
        badge_style = (
            "background:#dcfce7; color:#166534; border:1px solid #86efac;" if status_cls == "strong"
            else ("background:#fef9c3; color:#854d0e; border:1px solid #fde047;" if status_cls == "moderate"
                  else "background:#fee2e2; color:#991b1b; border:1px solid #fca5a5;")
        )
        retro_badge = " <span style='color:#dc2626; font-weight:bold;'>(R متراجع)</span>" if p_info["speed"] < 0 else ""
        planets_rows += f"""
        <tr>
            <td style="font-weight:800; font-size:15px;">{ALL_PLANETS_AR[p_name]}{retro_badge}</td>
            <td>{p_info['sign_name']} ({p_info['deg_in_sign']:.2f}°)</td>
            <td style="text-align:center;">البيت {p_info['whole_sign_house']}</td>
            <td style="text-align:center; font-weight:900; font-size:16px;">{sc:.1f} / 100</td>
            <td style="text-align:center;">
                <span style="padding:5px 12px; border-radius:20px; font-weight:700; font-size:12px; display:inline-block; {badge_style}">
                    {icon} {lbl}
                </span>
            </td>
            <td style="font-size:11.5px; color:#334155; line-height:1.7;">{reasons_html}</td>
        </tr>
        """

    outer_rows = ""
    for p_name in ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]:
        p_info = data["all_planets"][p_name]
        retro_txt = "متراجع (R)" if p_info["speed"] < 0 else "مستقيم (D)"
        outer_rows += f"""
        <tr>
            <td style="font-weight:700;">{ALL_PLANETS_AR[p_name]}</td>
            <td>{p_info['sign_name']} ({p_info['deg_in_sign']:.2f}°)</td>
            <td style="text-align:center;">البيت {p_info['whole_sign_house']}</td>
            <td style="text-align:center;">{retro_txt}</td>
        </tr>
        """

    bullets_html = "".join([f"<li>{b}</li>" for b in data["diag_bullets"]])
    
    recs_html = ""
    for r in data["recommendations"]:
        clean_r = r.replace("**", "")
        if r.startswith(("✨", "🏡", "💖", "🛠️", "👑", "👔", "🔥", "☀️", "🚀", "🌙", "🌹", "🌸", "⚡")):
            recs_html += f"<h4 style='color:#1e3a8a; margin:14px 0 6px 0;'>{clean_r}</h4>"
        else:
            recs_html += f"<p style='margin:4px 0 4px 12px;'>• {clean_r}</p>"

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>التقرير الفلكي الشامل - {data['name']}</title>
    <link href="https://fonts.googleapis.com/css2?family=Amiri:wght@700&family=Cairo:wght@400;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Cairo', sans-serif;
            direction: rtl;
            text-align: right;
            background: #f1f5f9;
            color: #0f172a;
            padding: 25px;
            margin: 0;
            font-size: 13.5px;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            background: #ffffff;
            padding: 35px;
            border-radius: 14px;
            border: 1px solid #cbd5e1;
            box-shadow: 0 6px 25px rgba(0,0,0,0.07);
        }}
        .header {{
            text-align: center;
            background: linear-gradient(135deg, #090d16 0%, #172554 100%);
            color: #f8fafc;
            padding: 25px;
            border-radius: 12px;
            border: 2px solid #d4af37;
            margin-bottom: 25px;
        }}
        .header h1 {{
            font-family: 'Amiri', serif;
            color: #facc15;
            font-size: 28px;
            margin: 0 0 6px 0;
        }}
        .section-title {{
            font-size: 17px;
            font-weight: 800;
            color: #0f172a;
            border-bottom: 2px solid #d4af37;
            padding-bottom: 6px;
            margin: 24px 0 14px 0;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }}
        .info-box {{
            background: #f8fafc;
            padding: 12px 14px;
            border-radius: 8px;
            border-right: 4px solid #d4af37;
            border: 1px solid #e2e8f0;
        }}
        .info-box span {{
            display: block;
            font-size: 11.5px;
            color: #64748b;
        }}
        .info-box strong {{
            font-size: 13.5px;
            color: #0f172a;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th {{
            background: #0f172a;
            color: #ffffff;
            padding: 10px 12px;
            text-align: right;
            font-weight: 700;
            font-size: 13px;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: top;
        }}
        .tag {{
            display: inline-block;
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            border-radius: 5px;
            padding: 2px 6px;
            margin: 2px;
            font-size: 11px;
        }}
        .power-summary {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 18px;
        }}
        .power-card {{
            background: #fefce8;
            border: 1px solid #fde047;
            border-radius: 10px;
            padding: 15px;
            text-align: center;
        }}
        .mercury-box {{
            background: #eff6ff;
            border-right: 5px solid #2563eb;
            padding: 14px 18px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-weight: 600;
        }}
        .diagnosis-box {{
            border-right: 6px solid {data['border_color']};
            background-color: {data['bg_tint']};
            border-top: 1px solid #e2e8f0;
            border-bottom: 1px solid #e2e8f0;
            border-left: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 22px;
            margin-bottom: 20px;
        }}
        .diagnosis-box h3 {{
            color: {data['title_color']};
            margin-top: 0;
            margin-bottom: 10px;
            font-size: 18px;
        }}
        .diagnosis-box ul {{
            margin: 10px 0 0 0;
            padding-right: 22px;
            line-height: 1.8;
        }}
        .rec-box {{
            background: #f8fafc;
            border-right: 5px solid #2563eb;
            padding: 18px;
            border-radius: 8px;
            margin-top: 20px;
            border: 1px solid #e2e8f0;
            line-height: 1.85;
        }}
        .rec-box h3 {{
            color: #1e3a8a;
            margin-top: 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #cbd5e1;
            color: #64748b;
            font-size: 12px;
        }}
        @media print {{
            body {{ background: #ffffff; padding: 0; }}
            .container {{ box-shadow: none; border: none; padding: 10px; max-width: 100%; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>التقرير الفلكي الشامل لقوى الكواكب وصلاحية الزواج</h1>
        <p>مقياس التقييم المئوي (100 نقطة) — الكرامات، اتصالات الكواكب العشرة، الكويكبات، والنجوم الثابتة الحقيقية — استرو رادار</p>
    </div>

    <div class="section-title">البيانات الفلكية والجغرافية للحدث</div>
    <div class="info-grid">
        <div class="info-box"><span>الاسم</span><strong>{data['name']}</strong></div>
        <div class="info-box"><span>الجنس</span><strong>{data['gender']}</strong></div>
        <div class="info-box"><span>التاريخ والوقت المحلي</span><strong>{data['birth_date']} ({data['birth_time_label']})</strong></div>
        <div class="info-box"><span>التوقيت العالمي (UTC)</span><strong>{data['utc_label']}</strong></div>
        <div class="info-box"><span>الموقع الجغرافي</span><strong>{data['location']}</strong></div>
        <div class="info-box"><span>الإحداثيات والمنطقة</span><strong>{data['coords_label']} ({data['tz_str']})</strong></div>
        <div class="info-box"><span>مرجعية الطالع والبيوت</span><strong>{data['asc_label']}</strong></div>
        <div class="info-box"><span>طبيعة الخريطة (الحيّز)</span><strong>{data['sect_label']}</strong></div>
    </div>

    <div class="section-title">تقييم الكواكب الشخصية الخمسة (مقياس 100 نقطة) وتفصيل الاتصالات</div>
    <table>
        <thead>
            <tr>
                <th style="width:12%;">الكوكب</th>
                <th style="width:14%;">البرج والدرجة</th>
                <th style="width:10%; text-align:center;">البيت</th>
                <th style="width:11%; text-align:center;">النتيجة</th>
                <th style="width:13%; text-align:center;">التصنيف</th>
                <th style="width:40%;">تفصيل الكرامات، اتصالات الكواكب، الكويكبات، والنجوم الثابتة</th>
            </tr>
        </thead>
        <tbody>
            {planets_rows}
        </tbody>
    </table>

    <div class="section-title">مواقع الكواكب العلوية والأجيال المؤثرة</div>
    <table>
        <thead>
            <tr>
                <th>الكوكب</th>
                <th>البرج والدرجة</th>
                <th style="text-align:center;">البيت</th>
                <th style="text-align:center;">حالة السير</th>
            </tr>
        </thead>
        <tbody>
            {outer_rows}
        </tbody>
    </table>

    <div class="section-title">مقارنة الكتل الطاقية (الأنوثة مقابل الذكورة)</div>
    <div class="power-summary">
        <div class="power-card">
            <div style="font-size:13px; color:#64748b;">مجموع طاقة الأنوثة (الزهرة + القمر من 200)</div>
            <div style="font-size:24px; font-weight:900; color:#be185d;">{data['fem_power']:.1f} نقطة</div>
        </div>
        <div class="power-card">
            <div style="font-size:13px; color:#64748b;">مجموع طاقة الذكورة (الشمس + المريخ من 200)</div>
            <div style="font-size:24px; font-weight:900; color:#1d4ed8;">{data['masc_power']:.1f} نقطة</div>
        </div>
    </div>

    <div class="mercury-box">
        🧠 <strong>حالة كوكب عطارد ({data['mercury_score']:.1f} / 100 — {data['mercury_label']}):</strong> {data['mercury_text']}
    </div>

    <div class="section-title">النتيجة التشخيصية للزواج والشراكة</div>
    <div class="diagnosis-box">
        <h3>{data['diag_title']}</h3>
        <p style="font-weight:700; margin-bottom:8px;">{data['diag_summary']}</p>
        <ul>{bullets_html}</ul>
    </div>

    <div class="rec-box">
        <h3>💡 التوصيات والإرشادات العملية وعلاجات تقوية الكواكب فلكياً:</h3>
        {recs_html}
    </div>

    <div class="footer">
        <p>معيار التصنيف المئوي: أكثر من 60 = قوي | من 50 إلى 60 = متوسط القوى | أقل من 50 = ضعيف — استرو رادار</p>
    </div>
</div>
</body>
</html>
"""
    return html

# =============================================================================
# 8. واجهة المستخدم التفاعلية في Streamlit
# =============================================================================
st.markdown("""
<div class="main-header">
    <h1>🔭 المحرك الفلكي المتقدم لتقييم قوى الكواكب وصلاحية الزواج</h1>
    <p>نظام تقييم شمولي من 100 نقطة يدمج الكرامات الخمس، اتصالات الكواكب العشرة، الكويكبات، والنجوم الثابتة الحقيقية</p>
    <p>تطوير الفلكي الدكتور استرو رادار</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("👤 البيانات الأساسية")
    name = st.text_input("الاسم أو عنوان الخريطة:", "سارة")
    gender = st.selectbox("الجنس:", ["أنثى", "ذكر"], index=0)
    birth_date = st.date_input(
        "تاريخ الميلاد / الحدث:",
        value=datetime.date(1995, 5, 15),
        min_value=datetime.date(1800, 1, 1),
        max_value=datetime.date(2100, 12, 31)
    )

    st.markdown("---")
    st.header("⏰ التوقيت المحلي")
    time_option = st.radio("دقة الساعة:", ["معرفة ساعة الميلاد", "عدم معرفة ساعة الميلاد"])
    
    birth_time_obj = datetime.time(12, 0, 0)
    if time_option == "معرفة ساعة الميلاد":
        birth_time_str = st.time_input("الساعة المحلية:", value=datetime.time(12, 0), step=300).strftime("%H:%M:%S")
        try:
            parts = list(map(int, birth_time_str.strip().split(":")))
            h = parts[0]
            m = parts[1] if len(parts) > 1 else 0
            s = parts[2] if len(parts) > 2 else 0
            birth_time_obj = datetime.time(h, m, s)
        except Exception:
            st.warning("⚠️ صيغة الوقت غير صحيحة، تم ضبط الوقت افتراضياً على 12:00:00.")
            birth_time_obj = datetime.time(12, 0, 0)

    st.markdown("---")
    st.header("🌍 الموقع الجغرافي")
    coord_mode = st.radio("طريقة تحديد الموقع:", ["اختيار من قائمة المدن", "إدخال الإحداثيات يدوياً (Lat/Lon)"])

    if coord_mode == "اختيار من قائمة المدن":
        selected_country_name = st.selectbox("الدولة:", country_list)
        country_code = country_map[selected_country_name]
        country_cities = cities_by_country.get(country_code, [])
        city_names = [c.name for c in country_cities]

        if city_names:
            selected_city_name = st.selectbox("المدينة:", city_names)
            selected_city = next((c for c in country_cities if c.name == selected_city_name), country_cities[0])
            lat = selected_city.latitude
            lon = selected_city.longitude
            location_label = f"{selected_city_name}, {selected_country_name}"
        else:
            lat, lon = 25.2048, 55.2708
            location_label = selected_country_name
    else:
        lat = st.number_input("خط العرض (Latitude):", min_value=-90.0, max_value=90.0, value=25.2048, format="%.4f")
        lon = st.number_input("خط الطول (Longitude):", min_value=-180.0, max_value=180.0, value=55.2708, format="%.4f")
        location_label = f"إحداثيات مخصصة ({lat:.4f}°, {lon:.4f}°)"

    tz_str = tf.timezone_at(lat=lat, lng=lon) or "UTC"
    st.info(f"📍 الإحداثيات: `{lat:.4f}°, {lon:.4f}°`\n\n⏰ المنطقة الزمنية: `{tz_str}`")

submit = st.button("🚀 تشغيل المحرك الفلكي وتوليد التقرير المئوي", type="primary")

if submit:
    local_tz = pytz.timezone(tz_str)
    has_birth_time = (time_option == "معرفة ساعة الميلاد")
    naive_dt = datetime.datetime.combine(birth_date, birth_time_obj if has_birth_time else datetime.time(12, 0))
    
    try:
        localized_dt = local_tz.localize(naive_dt, is_dst=None)
    except Exception:
        try:
            localized_dt = local_tz.localize(naive_dt, is_dst=False)
        except Exception:
            localized_dt = local_tz.localize(naive_dt)

    utc_dt = localized_dt.astimezone(pytz.utc)
    decimal_hour = utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, decimal_hour)

    raw_planets = {}
    for p_name, p_id in ALL_PLANETS_IDS.items():
        res, _ = swe.calc_ut(jd, p_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
        raw_planets[p_name] = {
            "lon": res[0],
            "lat": res[1],
            "speed": res[3]
        }

    if has_birth_time:
        _, ascmc = swe.houses_ex(jd, lat, lon, b'W')
        asc_lon = ascmc[0]
        house_start_sign = int(asc_lon / 30) % 12
        asc_label = f"الطالع: {ZODIAC_NAMES_AR[house_start_sign]} ({asc_lon % 30:.2f}°)"
    else:
        house_start_sign = int(raw_planets["Sun"]["lon"] / 30) % 12
        asc_label = f"طالع شمسي تقديري: {ZODIAC_NAMES_AR[house_start_sign]}"

    all_planets_data = {}
    for p_name, p_vals in raw_planets.items():
        p_lon = p_vals["lon"]
        sign_idx = int(p_lon / 30) % 12
        whole_sign_house = ((sign_idx - house_start_sign) % 12) + 1
        all_planets_data[p_name] = {
            "lon": p_lon,
            "speed": p_vals["speed"],
            "sign_idx": sign_idx,
            "sign_name": ZODIAC_NAMES_AR[sign_idx],
            "deg_in_sign": p_lon % 30,
            "whole_sign_house": whole_sign_house
        }

    sun_house = all_planets_data["Sun"]["whole_sign_house"]
    is_day_chart = (sun_house in [7, 8, 9, 10, 11, 12]) if has_birth_time else True
    sect_label = "خريطة نهارية (Diurnal)" if is_day_chart else "خريطة ليلية (Nocturnal)"

    asteroids_data = {}
    for ast_name, ast_id in ASTEROIDS_IDS.items():
        try:
            res, _ = swe.calc_ut(jd, ast_id, swe.FLG_SWIEPH)
            asteroids_data[ast_name] = {"lon": res[0]}
        except Exception:
            continue

    fixed_stars_data = compute_fixed_stars(jd)

    scores: Dict[str, float] = {}
    reasons: Dict[str, List[str]] = {}
    breakdowns: Dict[str, Dict[str, float]] = {}

    for p_name in PERSONAL_PLANETS:
        sc, r_list, b_dict = evaluate_planet_100_scale(
            planet_name=p_name,
            all_planets=all_planets_data,
            asteroids=asteroids_data,
            fixed_stars=fixed_stars_data,
            is_day_chart=is_day_chart,
            has_birth_time=has_birth_time
        )
        scores[p_name] = sc
        reasons[p_name] = r_list
        breakdowns[p_name] = b_dict

    st.markdown("---")
    st.markdown(f"### 📊 التحليل الفلكي الشامل لـ ({name}) — الجنس: ({gender}) — الموقع: ({location_label})")

    col_res1, col_res2 = st.columns([1.45, 1])
    with col_res1:
        st.markdown("#### ⭐ تقييم الكواكب الشخصية (من أصل 100 نقطة):")
        for p_name in PERSONAL_PLANETS:
            sc = scores[p_name]
            lbl, icon, _ = get_strength_classification(sc)
            p_info = all_planets_data[p_name]
            retro_tag = " [متراجع R]" if p_info["speed"] < 0 else ""
            st.markdown(f"""
            <div class="planet-detail-box">
                <strong>{ALL_PLANETS_AR[p_name]}{retro_tag}</strong>: 
                <code>{sc:.1f} / 100</code> — {icon} <strong>{lbl}</strong> | 
                برج {p_info['sign_name']} ({p_info['deg_in_sign']:.2f}°) — البيت {p_info['whole_sign_house']}<br>
                <span style="font-size:12px; color:#475569;">{' • '.join(reasons[p_name])}</span>
            </div>
            """, unsafe_allow_html=True)

    with col_res2:
        st.markdown("#### ℹ️ معطيات المحرك ومعايير القياس:")
        st.info(
            f"- **التوقيت العالمي (UTC):** `{utc_dt.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"- **اليوم اليولياني (JD):** `{jd:.5f}`\n"
            f"- **مرجعية الطالع:** {asc_label} (نظام كل برج بيت)\n"
            f"- **طبيعة الخريطة:** {sect_label}\n"
            "- **نطاقات التقييم المئوي:**\n"
            "  - 🟢 **أكثر من 60 نقطة:** قوي\n"
            "  - 🟡 **من 50 إلى 60 نقطة:** متوسط القوى\n"
            "  - 🔴 **أقل من 50 نقطة:** ضعيف"
        )

    sun_sc = scores["Sun"]
    moon_sc = scores["Moon"]
    mercury_sc = scores["Mercury"]
    venus_sc = scores["Venus"]
    mars_sc = scores["Mars"]

    is_sun_strong = sun_sc > 60.0
    is_moon_strong = moon_sc > 60.0
    is_mercury_strong = mercury_sc > 60.0
    is_venus_strong = venus_sc > 60.0
    is_mars_strong = mars_sc > 60.0

    fem_power = round(venus_sc + moon_sc, 1)
    masc_power = round(sun_sc + mars_sc, 1)

    st.markdown("---")
    st.markdown("### ⚖️ موازين القوى والتشخيص النهائي:")
    c_p1, c_p2 = st.columns(2)
    c_p1.metric("مجموع طاقة الأنوثة (الزهرة + القمر من 200)", f"{fem_power:.1f} نقطة")
    c_p2.metric("مجموع طاقة الذكورة (الشمس + المريخ من 200)", f"{masc_power:.1f} نقطة")

    mercury_lbl, _, _ = get_strength_classification(mercury_sc)
    if is_mercury_strong:
        mercury_text = f"عطارد قوي ({mercury_sc:.1f}/100): رجاحة عقل وسرعة فهم وحسن تواصل."
        st.success(f"🟢 **{mercury_text}**")
    elif 50.0 <= mercury_sc <= 60.0:
        mercury_text = f"عطارد {mercury_lbl} ({mercury_sc:.1f}/100): التواصل الفكري متوازن ويحتاج لتركيز."
        st.warning(f"🟡 **{mercury_text}**")
    else:
        mercury_text = f"عطارد {mercury_lbl} ({mercury_sc:.1f}/100): يحتاج إلى جهد واعٍ في تنظيم الأفكار."
        st.error(f"🔴 **{mercury_text}**")

    diag_title = ""
    diag_summary = ""
    diag_bullets = []
    border_color = "#d4af37"
    bg_tint = "#ffffff"
    title_color = "#0f172a"

    if gender == "أنثى":
        if fem_power <= masc_power:
            diag_title = "❌ لا تصلح للزواج لأن طاقة الذكورة مرتفعة"
            diag_summary = f"مجموع الزهرة والقمر ({fem_power:.1f}) ≤ مجموع الشمس والمريخ ({masc_power:.1f}):"
            diag_bullets = [
                "طاقة الذكورة والسيطرة والاستقلالية تطغى على الطبيعة الأنثوية.",
                "يصعب عليها التكيف مع متطلبات الزواج التقليدي أو الخضوع لسلطة الزوج."
            ]
            border_color = "#ef4444"
            bg_tint = "#fef2f2"
            title_color = "#991b1b"
        elif is_venus_strong and is_moon_strong and (fem_power > masc_power):
            diag_title = "✅ تصلح للزواج، الإنجاب، رعاية الأطفال، التدبير المنزلي، والأنوثة"
            diag_summary = f"زهرة قوية ({venus_sc:.1f}) + قمر قوي ({moon_sc:.1f}):"
            diag_bullets = [
                "أنوثة مكتملة واهتمام بالزينة والعناية بالمظهر.",
                "أمومة واعية وقدرة عالية على رعاية الأطفال وتربيتهم بالحنان.",
                "ربة منزل بارعة وإشاعة الدفء والاستقرار الأسري."
            ]
            border_color = "#16a34a"
            bg_tint = "#f0fdf4"
            title_color = "#166534"
        else:
            diag_title = "🟡 صلاحية متوسطة أو خاصة للزواج"
            diag_summary = f"مجموع الأنوثة ({fem_power:.1f}) مقابل الذكورة ({masc_power:.1f}):"
            diag_bullets = ["تؤدي الواجبات الزوجية والمنزلية بصورة معتدلة."]
            border_color = "#2563eb"
            bg_tint = "#eff6ff"
            title_color = "#1e40af"
    else:
        if (masc_power <= fem_power) or (sun_sc <= 60.0 and mars_sc <= 60.0):
            diag_title = "❌ لا يصلح للزواج"
            diag_summary = f"مجموع الذكورة ({masc_power:.1f}) غير كافٍ أو منخفض:"
            diag_bullets = ["ضعف في مقومات القيادة وتحمل المسؤولية الزوجية والمادية."]
            border_color = "#ef4444"
            bg_tint = "#fef2f2"
            title_color = "#991b1b"
        else:
            diag_title = "👑 يصلح للزواج والقيادة والعمل الشاق والإنجاب بامتياز"
            diag_summary = f"الشمس والمريخ كلاهما قويان (الشمس: {sun_sc:.1f}، المريخ: {mars_sc:.1f}):"
            diag_bullets = ["يجمع ببراعة بين هيبة القيادة (الشمس) والقوة البدنية والإنجاب (المريخ)."]
            border_color = "#16a34a"
            bg_tint = "#f0fdf4"
            title_color = "#166534"

    bullets_ui = "".join([f"<li>{b}</li>" for b in diag_bullets])
    st.markdown(f"""
    <div class="result-card" style="border-right-color: {border_color}; background-color: {bg_tint};">
        <h3 style="color: {title_color}; margin-top: 0;">{diag_title}</h3>
        <p><strong>{diag_summary}</strong></p>
        <ul>{bullets_ui}</ul>
    </div>
    """, unsafe_allow_html=True)

    recommendations = get_advanced_recommendations(
        gender, venus_sc, moon_sc, sun_sc, mars_sc, fem_power, masc_power
    )
    
    st.markdown("""
    <div class="rec-box">
        <h3>💡 التوصيات والإرشادات العملية وعلاجات تقوية الكواكب فلكياً:</h3>
    </div>
    """, unsafe_allow_html=True)
    for rec in recommendations:
        if rec.startswith(("✨", "🏡", "💖", "🛠️", "👑", "👔", "🔥", "☀️", "🚀", "🌙", "🌹", "🌸", "⚡")):
            st.markdown(f"#### {rec}")
        else:
            st.markdown(f"- {rec}")

    report_payload = {
        "name": name,
        "gender": gender,
        "birth_date": birth_date.strftime("%Y-%m-%d"),
        "birth_time_label": str(birth_time_obj) if has_birth_time else "غير محددة",
        "utc_label": utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "location": location_label,
        "coords_label": f"{lat:.4f}°, {lon:.4f}°",
        "tz_str": tz_str,
        "asc_label": asc_label,
        "sect_label": sect_label,
        "all_planets": all_planets_data,
        "scores": scores,
        "reasons": reasons,
        "fem_power": fem_power,
        "masc_power": masc_power,
        "mercury_score": mercury_sc,
        "mercury_label": mercury_lbl,
        "mercury_text": mercury_text,
        "diag_title": diag_title,
        "diag_summary": diag_summary,
        "diag_bullets": diag_bullets,
        "recommendations": recommendations,
        "border_color": border_color,
        "bg_tint": bg_tint,
        "title_color": title_color
    }

    html_report = generate_html_report(report_payload)

    st.download_button(
        label=f"📥 تحميل تقرير التحليل الفلكي الشامل لـ ({name}) [HTML جاهز للطباعة]",
        data=html_report,
        file_name=f"تقرير_القوى_الفلكية_{name.replace(' ', '_')}.html",
        mime="text/html",
        use_container_width=True
    )
