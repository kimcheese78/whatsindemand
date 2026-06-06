"""Assign subcategories to all remaining verified skills (2,428 NULL subcategories).
Also recategorizes a handful of misplaced skills.

Run:
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/subcategorize_all.py
    DATABASE_URL='postgresql://...' PYTHONPATH=. venv/bin/python scripts/subcategorize_all.py --apply
"""
import os, sys
PROD_DSN = 'postgresql://postgres:gnhrxOkYHTPaEIYuetmcXptfkTcvnLPp@switchyard.proxy.rlwy.net:48202/railway'
os.environ.setdefault('DATABASE_URL', PROD_DSN)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
from app import create_app
from app.models import db, Skill
app = create_app()
APPLY = '--apply' in sys.argv

# ─── RECATEGORIZATIONS (category changes needed before subcategory) ───────────
# id → (new_category, subcategory)
RECAT = {
    952:  ('technical', 'Enterprise Tools & Platforms'),  # Application Services
    1788: ('technical', 'Enterprise Tools & Platforms'),  # Accounting Software
    1789: ('technical', 'Enterprise Tools & Platforms'),  # Accounting Systems
    525:  ('technical', 'Enterprise Tools & Platforms'),  # Office 365 Exchange Online
    506:  ('technical', 'Cloud & Infrastructure'),        # Platform Engineering
    509:  ('technical', 'Cloud & Infrastructure'),        # Site Reliability Engineering
    3582: ('technical', 'Enterprise Tools & Platforms'),  # Mailchimp
    3704: ('technical', 'Hardware & Embedded'),           # In-Plane Switching (IPS)
    1330: ('technical', 'AI & Machine Learning'),         # Text Classification
    2244: ('technical', 'Networking & Systems'),          # Telemetry (IoT context)
    931:  ('technical', 'Databases & Data Engineering'),  # Operational Data Store
    3661: ('technical', 'Hardware & Embedded'),           # Audio Signal Processing
    3664: ('technical', 'Enterprise Tools & Platforms'),  # Audio Compression
    3659: ('technical', 'Enterprise Tools & Platforms'),  # Audio Editing Software
    4142: ('technical', 'Hardware & Embedded'),           # Barcode Readers
}

# ─── SUBCATEGORY ASSIGNMENTS ──────────────────────────────────────────────────
# Grouped for readability. Last write wins for duplicate IDs.

A = {}  # id → subcategory

# ══ SOFT ══════════════════════════════════════════════════════════════════════

_personal = [401,102,103,418,403,408,409,410,411,1095,417,1096,1091,1102,49,
             3739,3735,3745,3742,3734,3752,3740,3754,3747,3746,3736,3738,3743,3750,3749,3741,3753]
_comm     = [3324,3340,3330,3344,1093,3325,3341,3354,3338,3342,3335,3334,394]
_collab   = [44,414,435,436,423,422,425,424,1092,1097,1098,1099,1094,1100,47,396]
_problem  = [427,433,396]
for _i in _personal: A[_i] = 'Personal Effectiveness'
for _i in _comm:     A[_i] = 'Communication'
for _i in _collab:   A[_i] = 'Collaboration & Teamwork'
for _i in _problem:  A[_i] = 'Problem Solving & Critical Thinking'
A[49]  = 'Leadership & Management'   # Project Management
A[394] = 'Troubleshooting' ; A[394] = 'Problem Solving & Critical Thinking'
A[396] = 'Problem Solving & Critical Thinking'  # Data-Driven Decision Making

# ══ DOMAIN ════════════════════════════════════════════════════════════════════

# Industries — healthcare/clinical
_ind_health = [
    2028,2042,2016,2143,2015,2014,2172,2023,2055,2075,2178,2074,2039,2036,
    2221,2217,2267,2067,2133,1295,2264,2268,2346,2022,2024,2170,2021,2054,
    2018,2293,2137,2233,2245,2056,2013,2094,2026,2300,2109,2092,352,2126,
    2107,2132,2135,2260,2163,1294,2050,2031,2129,2130,2134,2141,2266,2231,
    2177,355,2124,2034,3837,2320,2047,2048,2275,2234,2165,2302,2304,2044,
    2070,2076,2322,2025,2083,2262,2200,2195,2191,2207,2219,2222,2188,
    2316,2321,2232,3849,2243,2263,2276,2038,2033,2121,2240,2174,2249,
    2108,2247,2068,2122,2128,2087,2164,2071,2065,2171,2330,2115,2242,
    2253,2045,2248,2254,2141,2230,2278,2050,2331,2306,2342,2236,2296,
    2192,2309,2131,2123,2190,2085,2303,2310,2089,1292,1351,2038,2050,
    2043,2096,2082,2095,2097,2079,2073,2072,2116,2090,2106,2193,2311,
    2313,2324,356,2127,2294,2098,2120,2295,2105,351,2286,2086,2358,2093,
    2239,2030,2289,1317,2139,2141,2266,2218,2076,2322,1290,2114,2296,
    2238,2121,2243,2251,2250,2255,2331,2306,2050,2342,2052,2236,
    2157,4126,4128,2142,2161,1349,2333,1785,3841,2337,2179,2343,2347,
    2235,2223,2069,2349,2153,2325,2332,2173,2284,2052,2263,2131,
    2179,2088,2327,2335,2326,2354,1763,2328,2345,2100,2348,2344,
    2272,2281,2277,2319,2291,2287,2285,2292,2114,2296,2292,2131,
    2040,2016,1282,2342,2050,2262,2200,2195,1386,4114,2215,
    2029,2041,2241,2091,2064,2168,2063,2176,1782,2317,2202,
    2313,4115,2163,1283,2025,1738,1742,1739,2338,2288,
    4131,4133,2032,4187,4185,2259,2057,2175,2066,2061,
    2258,2060,2039,2036,2298,4125,2298,2189,2166,2062,
    2113,2214,2210,2199,1231,2227,2205,2208,2170,2021,
    2018,2293,2021,352,2126,2239,2289,2030,1361,
    4186,4187,4188,4189,4190,4191,4192,4193,4194,4195,4196,4197,4198,4199,
    2230,2278,1334,1337,4129,4127,4117,4118,4120,962,1229,1747,
    3835,4116,1780,1737,1265,1268,1242,1237,1241,1226,1261,1240,
    1236,1201,1259,1232,2314,2315,2316,2321,3847,1247,2051,
    926,2101,1769,1784,1755,1740,2157,1349,1257,1277,1278,
    1280,1276,1275,1736,1730,1729,1727,1726,1725,1731,1738,
    1744,1743,1756,1749,1750,1748,1732,1733,1767,1760,1761,
    1754,1745,1764,357,359,2358,2093,2360,2359,
    872,1349,4138,4137,3848,1203,1201,1252,4176,
    1203,1192,3858,3856,
]
for _i in _ind_health: A[_i] = 'Industries'

# Industries — non-healthcare
_ind_other = [
    1780,4131,4133,2102,1737,1742,1739,357,1311,1261,1240,1226,2358,
    2093,2360,2359,926,2101,1769,1784,1755,1740,1257,1277,1278,1280,
    1276,1275,1736,1730,1729,1727,1726,1725,1731,1738,1744,1743,1756,
    1749,1750,1748,1732,1733,1767,1760,1761,1754,1745,1764,
    1263,1242,1237,1241,1268,1236,1259,1232,1201,1265,1247,
    962,1229,4117,4118,4120,4127,4129,4128,4130,
    3835,1734,1772,1770,1771,4116,2322,1249,1267,
    1751,1735,1739,1741,1271,1281,4115,2317,1273,
    1779,1778,1780,1252,2315,2316,4174,4175,4179,
    4138,4137,3848,3849,1203,1769,
]
for _i in _ind_other: A[_i] = 'Industries'

# Business & Operations
_biz = [
    940,275,953,892,86,997,904,873,922,981,855,1044,899,877,856,864,
    276,923,878,944,879,874,999,868,4167,4148,988,1073,1063,871,870,
    852,1009,935,1283,863,897,1065,4157,995,3586,3593,1329,948,908,
    869,976,872,929,959,3843,1218,4150,949,3860,967,1043,3855,876,
    950,1003,1002,969,888,998,1048,970,978,993,951,4136,4153,1029,
    1037,884,1070,1062,1064,1072,1060,1081,1028,1068,1076,1061,1067,
    1079,1077,1084,1339,1343,1340,1344,1057,1069,1066,895,1074,1071,
    985,3579,924,973,972,1001,968,980,977,994,1087,1038,1045,875,
    963,1090,1089,859,1010,1035,880,966,862,971,857,1049,
    4165,4171,938,941,1058,1046,946,1007,1006,3854,3857,
    4152,5217,869,4177,4151,514,515,517,510,520,
    860,2350,3838,3839,3837,2320,1082,3602,3590,3591,3594,
    886,3843,1218,4150,511,512,4173,858,1030,
    1231,4174,4175,4179,1040,1195,1197,4165,4171,
    4147,826,1031,1042,1041,4156,1050,3663,909,3731,
    1343,1340,1339,1344,1084,1070,1077,1062,1064,
    1072,1060,1081,1028,1068,1076,1061,1067,1079,
    3579,924,973,972,1001,968,980,977,994,
    1083,1333,1231,960,3876,1208,4159,860,
    845,3836,982,947,1058,866,282,3855,875,
    958,875,875,1223,3861,
]
for _i in _biz: A[_i] = 'Business & Operations'

# Finance & Accounting
_fin = [
    508,982,1199,1194,1187,1202,1185,1193,1216,1207,1198,1204,1189,
    1206,1765,1192,4166,965,1032,3876,1208,1196,1879,339,1009,
    929,967,971,857,1000,979,1853,1831,3836,925,197,3667,
    1210,1188,856,995,1004,1058,1195,1197,1903,1904,
]
for _i in _fin: A[_i] = 'Finance & Accounting'

# Sales & Customer Success
_sales = [
    86,904,899,87,88,89,261,974,986,866,282,1031,1003,
    3860,3864,3877,3858,284,3577,
]
for _i in _sales: A[_i] = 'Sales & Customer Success'

# Marketing & Growth
_mkt = [
    3593,3670,3669,3668,286,3583,3716,885,3677,3586,3576,3698,
    3666,3693,3703,3684,3691,3672,3580,3589,3645,3631,3627,3632,
    3628,3629,3633,3634,3635,3636,3637,3638,3639,3641,3643,3644,
    3584,3650,3609,3610,3612,3611,3613,3614,3615,3616,3617,3618,
    3619,3620,3621,3622,3625,3626,3591,1196,960,3596,3603,3604,
    3605,3606,3607,990,1273,3590,3594,3581,3649,3704,
    3332,3568,3588,3587,1332,3861,991,
]
for _i in _mkt: A[_i] = 'Marketing & Growth'

# Legal & Compliance
_legal = [
    334,346,1298,2119,4116,1258,1220,2111,1781,1289,4119,1297,
    1264,1775,1759,1750,1775,1732,1776,1748,3845,2113,1310,
    1773,893,3852,4178,3390,3393,3394,3395,3396,3397,3398,3399,
    3843,3854,3857,3855,3851,3856,3840,3842,3849,1260,1224,
    3847,2112,1222,4125,1225,1304,5076,927,351,2120,
    2118,2122,1879,2122,2363,889,1215,1774,1777,
    4176,1004,925,2113,2018,2118,2176,2122,4153,
    3446,1000,1049,862,1902,1215,
]
for _i in _legal: A[_i] = 'Legal & Compliance'

# People & HR
_phr = [
    1298,1371,3713,1304,1387,1319,1285,1320,1328,1325,1227,1284,
    1378,1322,1314,1323,1270,1263,1265,1296,1299,1388,1297,
    1341,1366,2367,1316,1255,1329,1368,1324,1381,1385,1391,
    1369,1354,1313,1375,1370,1335,1333,1293,1285,1286,1362,
    1360,1376,1365,1301,1356,1388,1379,2192,2216,1237,1270,
    4122,2198,1293,1388,1321,3728,3733,3717,3724,1231,
    1300,1388,1290,3715,3711,2216,1315,1284,3718,3719,
    3720,3731,3727,3726,3730,1380,1353,1301,1326,1312,
    2363,2206,2201,2202,1282,1292,1351,2198,3676,
    1321,1382,1372,1389,1390,2192,888,998,
    2367,1388,1389,1390,1391,2216,1362,1377,
    1319,1325,1377,1320,1328,1377,1302,1367,
    3721,3677,3675,3716,1375,1356,2192,
    1051,3590,604,909,3731,3727,3726,
    1083,3579,924,1338,1333,
]
for _i in _phr: A[_i] = 'People & HR'

# Product & Design
_prod = [
    3695,3696,3653,3651,3662,3683,3697,3703,3684,3693,3708,3680,
    3691,3672,3685,3676,3690,3682,3654,3658,3663,3679,3694,3723,
    3712,3722,3705,3699,3706,3702,3707,3688,3701,3700,3709,3709,
    3686,3689,3692,3653,3655,3656,3660,3657,3659,1247,1318,
    3580,1243,1052,264,3639,1332,1273,
]
for _i in _prod: A[_i] = 'Product & Design'

# Methodologies (domain)
_meth = [
    854,1310,2110,4173,1075,1085,1088,1036,1391,
]
for _i in _meth: A[_i] = 'Methodologies'

# ══ TECHNICAL ═════════════════════════════════════════════════════════════════

# AI & Machine Learning
_ai = [
    5213,5214,5215,5216,5218,5219,
    2452,2444,2450,2468,2454,2436,2432,2435,2473,2474,3181,2471,
    2443,2438,689,2466,2476,2451,2445,627,2461,2456,
    2453,668,660,822,2467,2458,2465,766,768,
    2431,705,650,638,637,2465,816,817,
    3026,3087,612,635,631,
    590,680,686,687,688,763,767,
    775,779,785,787,792,
    616,617,609,624,625,627,628,629,630,
    631,632,633,634,636,638,641,642,643,644,648,649,650,651,
    652,653,654,655,657,658,660,661,666,667,668,
    3040,2458,2460,2471,2473,2474,2431,
]
for _i in _ai: A[_i] = 'AI & Machine Learning'
# Fix misassigned from above
A[624] = 'Graph Algorithms' ; A[624] = 'Data Science & Analytics'
A[636] = 'Data Science & Analytics'  # Data Reduction
A[637] = 'Data Science & Analytics'  # Information Processing
A[638] = 'Data Science & Analytics'  # Markov Chain
A[641] = 'Databases & Data Engineering'  # Data Blending
A[642] = 'Data Science & Analytics'  # Knowledge Discovery
A[643] = 'Data Science & Analytics'  # Information Retrieval
A[644] = 'Data Science & Analytics'  # Causal Inference
A[648] = 'Data Science & Analytics'  # Technical Analysis
A[649] = 'Data Science & Analytics'  # Normalization
A[650] = 'Data Science & Analytics'  # Monte Carlo
A[651] = 'Databases & Data Engineering'  # Data Engineering
A[652] = 'Data Science & Analytics'  # Complexity Theory
A[653] = 'Data Science & Analytics'  # Weka
A[654] = 'Databases & Data Engineering'  # Data Capture
A[655] = 'Databases & Data Engineering'  # Data Selection
A[657] = 'Databases & Data Engineering'  # Jupyter Notebook
A[658] = 'Databases & Data Engineering'  # Metadata (already set)
A[660] = 'AI & Machine Learning'   # Naive Bayes Classifier
A[661] = 'Data Science & Analytics'
A[666] = 'Data Science & Analytics'  # Pyspark
A[667] = 'Data Science & Analytics'  # MCMC
A[668] = 'AI & Machine Learning'   # Naive Bayes
A[624] = 'Data Science & Analytics'

# Programming Languages
_prog = [
    120,2917,3033,3004,2917,3118,3080,3079,3067,3117,3081,3071,3127,
    2565,3023,2583,3163,3186,3056,3061,3062,3058,3076,3009,
    2545,2546,2547,2577,2578,2581,2576,2988,3026,3025,
    3022,3019,3018,3017,3016,3015,3010,3007,3006,3004,3002,3001,
    2999,2998,2997,2995,2993,2992,2991,2990,2989,2987,2986,2985,
    2984,2983,2982,2981,2980,2979,2978,
    2917,2916,2915,2914,2912,2910,2909,2908,2907,2906,2905,2904,2903,
    2902,2901,2900,2899,2898,2897,2896,2895,2894,2893,2892,2891,2890,
    2889,2888,2887,2886,
    3305,3286,3285,3293,3289,3283,3282,3281,3280,3279,3278,3277,3276,3275,
    584,597,574,589,571,590,570,580,582,583,579,
    604,591,592,593,595,596,598,599,600,601,602,603,
    2460,2459,2458,2500,
    484,473,480,483,496,493,3154,3137,3020,
]
for _i in _prog: A[_i] = 'Programming Languages'

# Data Science & Analytics
_ds = [
    10,590,591,592,595,596,598,599,600,601,603,604,
    571,574,579,580,582,583,589,
    680,681,683,684,685,686,688,693,694,695,
    696,697,698,699,700,701,703,704,705,706,707,708,709,710,711,712,
    713,714,715,716,717,718,719,720,721,722,723,724,725,726,727,728,
    729,730,731,732,733,734,735,736,737,738,739,740,741,742,
    743,744,745,746,747,748,749,750,751,752,753,754,755,756,757,758,
    759,760,761,762,763,764,765,766,767,768,769,770,771,772,773,774,
    775,776,777,778,779,780,781,782,783,784,785,786,787,788,789,790,
    791,792,793,794,795,796,797,798,799,800,801,802,803,804,805,806,
    807,808,809,810,811,812,813,814,815,816,817,818,819,820,821,
    4079,4082,4083,4084,4085,4086,4088,4089,4090,4091,4092,4093,
    4094,4095,4096,4097,4098,4099,4100,4101,4103,4104,4105,4106,
    4107,4108,4109,4110,4111,4112,4014,4015,
    672,673,674,675,677,678,679,
    556,543,541,545,548,549,550,551,553,554,555,557,558,559,560,
    561,562,563,564,565,566,567,568,569,570,
    590,609,610,611,612,613,614,615,616,617,618,619,620,621,622,
    623,624,625,626,627,628,629,630,631,632,633,634,635,636,637,638,
    639,640,641,642,643,644,645,646,647,648,649,650,651,652,653,654,
    655,657,658,659,660,661,
    2836,2830,2831,2832,2833,2834,2835,2837,2838,2839,2840,2841,2842,
    2843,2844,2845,2846,2847,
    3940,3939,4005,4008,4009,4010,4011,4013,4017,4018,4019,4020,
    4021,4022,4023,4024,4025,4026,4027,4028,4029,4030,4031,4032,
    4033,4034,4035,4036,4037,4038,4039,4040,4041,4042,4043,4044,
    4045,4046,4047,4048,4050,4051,4052,4053,4054,4055,4056,4057,
    4058,4059,4060,4061,4062,4063,4064,4065,4066,4067,4068,4069,
    4070,4071,4072,4073,4074,4075,4076,4077,4078,
    4000,4001,4002,4003,4004,4006,4007,4012,
    3880,3881,3882,3883,3884,3885,3886,3887,3888,3889,3890,3891,
    3892,3893,3894,3895,3896,3897,3898,3899,3900,3901,3902,3903,
    3904,3905,3906,3907,3908,3909,3910,3911,3912,3913,3914,3915,
    3916,3917,3918,3919,3920,3921,3922,3923,3924,3925,3926,3927,
    3928,3929,3930,3931,3932,3933,3934,3935,3936,3937,3938,3939,
    3940,3941,3942,3943,3944,3945,3946,3947,3948,3949,3950,3951,
    3952,3953,3954,3955,3956,3957,3958,3959,3960,3961,3962,3963,
    3964,3965,3966,3967,3968,3969,3970,3971,3972,3973,3974,3975,
    3976,3977,3978,3979,3980,3981,3982,3983,3984,3985,3986,3987,
    3988,3989,3990,3991,3992,3993,3994,3995,3996,3997,3998,3999,
]
for _i in _ds: A[_i] = 'Data Science & Analytics'

# Databases & Data Engineering
_db = [
    2710,2706,2704,2703,2702,2701,2700,2699,2698,2697,2696,2695,
    2694,2693,2692,2691,2690,2689,2688,2687,2686,2685,2684,2683,
    2682,2681,2680,2679,2678,2677,2676,2675,2674,2673,2672,
    2760,2761,2762,2763,2764,2765,2766,2767,2768,2769,2770,2771,
    2772,2773,2774,2775,2776,2777,2778,2779,2780,2781,2782,2783,
    2784,2785,2786,2787,2788,2789,2790,2791,2792,2793,2794,2795,
    2796,2797,2798,2799,2800,
    669,670,671,672,681,
    3112,641,654,655,
    2520,
]
for _i in _db: A[_i] = 'Databases & Data Engineering'
A[670] = 'AI & Machine Learning'   # Real Time Data
A[681] = 'Data Science & Analytics'  # Histogram
A[671] = 'Data Science & Analytics'  # Snowflake Schema

# Cloud & Infrastructure (technical)
_cloud = [
    2509,2510,2511,2512,2513,2514,2515,2516,2517,2518,2519,2520,
    2521,2522,2523,2524,2525,2526,2527,2528,2529,2530,2531,2532,
    2533,2534,2535,2536,2537,2538,2539,2540,2541,2542,2543,2544,
    2545,
    3264,3265,3266,3267,3268,3269,3270,3271,3272,3273,
    509,506,  # recategorized from domain
    2852,2853,2854,2855,2856,2857,2858,2859,2860,2861,2862,2863,
    2864,2865,2866,2867,2868,2869,2870,2871,2872,2873,2874,2875,
    2876,2877,2878,2879,
]
for _i in _cloud: A[_i] = 'Cloud & Infrastructure'
A[2545] = 'Programming Languages'  # Compilers
A[2852] = 'Hardware & Embedded'   # Mechanization

# Networking & Systems
_net = [
    2940,2941,2942,2943,2944,2945,2946,2947,2948,2949,2950,2951,
    2952,2953,2954,2955,2956,2957,2958,2959,2960,2961,2962,2963,
    2964,2965,2966,2967,2968,2969,2970,2971,2972,2973,2974,2975,
    2976,2977,2978,2979,2980,
    3226,3227,3228,3229,3230,3231,3232,3233,3234,3235,3236,3237,
    3238,3239,3240,3241,3242,3243,3244,3245,3246,3247,3248,3249,
    3250,3251,3252,3253,3254,3255,3256,3257,3258,3259,3260,3261,
    3262,3263,
    2800,2801,2802,2803,2804,2805,2806,2807,2808,2809,2810,2811,
    2812,2813,2814,2815,2816,2817,2818,2819,2820,2821,2822,2823,
    2824,2825,2826,2827,2828,
    2481,2482,2483,2484,2486,2487,2488,2489,2490,2491,2492,2493,
    2494,2495,2496,2497,2498,2499,2500,2501,2502,2503,2504,2505,
    2506,2507,2508,
    2244,931,  # recategorized
    3040,3041,3042,3043,3044,3045,3046,3047,3048,3049,3050,3051,
    3052,3053,3054,3055,
]
for _i in _net: A[_i] = 'Networking & Systems'
A[3040] = 'Enterprise Tools & Platforms'  # Bing Search
A[3044] = 'Backend & APIs'  # Server-Side
A[3043] = 'Backend & APIs'  # Web Servers
A[3045] = 'Networking & Systems'  # File Servers
A[3046] = 'Enterprise Tools & Platforms'  # Microsoft Exchange
A[3047] = 'DevOps & CI/CD'  # WildFly
A[3048] = 'Cloud & Infrastructure'  # Server Farms
A[3049] = 'Cloud & Infrastructure'  # Akamai
A[3050] = 'Networking & Systems'  # Linux Servers
A[3051] = 'Networking & Systems'  # Server Administration
A[3052] = 'DevOps & CI/CD'  # Application Lifecycle Management
A[3053] = 'Data Science & Analytics'  # Scientific Computing
A[3054] = 'Data Science & Analytics'  # Program Optimization
A[3055] = 'DevOps & CI/CD'  # Open-Source Software
A[2481] = 'Cloud & Infrastructure'  # Backup and Restore
A[2482] = 'Hardware & Embedded'  # Backup Devices
A[2483] = 'Enterprise Tools & Platforms'  # Desktop Computing
A[2484] = 'Networking & Systems'  # Personal Computers
A[2486] = 'Programming Languages'  # Plain Text
A[2487] = 'Networking & Systems'  # Digital Data
A[2488] = 'Mobile'  # Mobile Phones
A[2489] = 'Networking & Systems'  # Computer Literacy
A[2490] = 'Networking & Systems'  # Firefox
A[2491] = 'Networking & Systems'  # Digital Literacy
A[2492] = 'Networking & Systems'  # Web Browsers
A[2493] = 'Networking & Systems'  # Online Communication
A[2494] = 'Mobile'  # Smartphone Operation
A[2495] = 'Networking & Systems'  # Digital Technology
A[2496] = 'Blockchain & Web3'  # Ethereum → use Security or Programming?
A[2497] = 'Security & Compliance'  # NFT → keep in tech, Security/Blockchain
A[2498] = 'Security & Compliance'  # Hyperledger
A[2499] = 'Programming Languages'  # C
A[2500] = 'Programming Languages'  # C++ Concepts
A[2501] = 'Programming Languages'  # C++
A[2502] = 'Programming Languages'  # Standard Template Library
A[2503] = 'Cloud & Infrastructure'  # Cloud Technologies
A[2504] = 'Cloud & Infrastructure'  # Remote Infrastructure Management
A[2505] = 'Security & Compliance'  # Cloud Computing Security
A[2506] = 'Cloud & Infrastructure'  # Cloud Migration
A[2507] = 'Cloud & Infrastructure'  # Autoscaling
A[2508] = 'Cloud & Infrastructure'  # Cloud Computing
A[2496] = 'Security & Compliance'   # Ethereum → blockchain context security
A[2244] = 'Networking & Systems'

# Security & Compliance (technical)
_sec = [
    2600,2601,2602,2603,2604,2605,2606,2607,2608,2609,2610,2611,2612,
    2613,2614,2615,2616,2617,2618,2619,2620,2621,2622,2623,2624,2625,
    2626,2627,2628,2629,2630,2631,2632,2633,2634,2635,2636,2637,2638,
    2639,2640,2641,2642,2643,2644,2645,2646,2647,2648,2649,2650,2651,
    2652,2653,2654,2655,2656,2657,2658,2659,2660,2661,2662,2663,2664,
    2665,2666,2667,2668,2669,2670,2671,2672,2673,2674,2675,2676,
    2430,2429,2428,2427,
]
for _i in _sec: A[_i] = 'Security & Compliance'
A[2600] = 'Cloud & Infrastructure'  # Desired State Configuration
A[2601] = 'Networking & Systems'   # Ifconfig
A[2602] = 'Enterprise Tools & Platforms'  # System Center Config Manager
A[2603] = 'Enterprise Tools & Platforms'  # Joomla
A[2604] = 'Frontend & Web'  # WordPress
A[2605] = 'Frontend & Web'  # Content Management Systems
A[2606] = 'Enterprise Tools & Platforms'  # Authoring Systems
A[2627] = 'Security & Compliance'  # Cipher
A[2628] = 'Security & Compliance'  # Social Engineering
A[2676] = 'Data Science & Analytics'  # Web Scraping
A[2430] = 'Security & Compliance'  # PAM
A[2429] = 'Databases & Data Engineering'  # Java Persistence API
A[2428] = 'Backend & APIs'  # Application Programming Interface

# Hardware & Embedded
_hw = [
    1407,1396,1401,1402,1403,1404,1405,1406,1408,1409,1410,1411,1412,
    1413,1414,1415,1416,1417,1418,1419,1420,1421,1422,1423,1424,1425,
    1426,1427,1428,1429,1430,1431,1432,1433,1434,1435,1436,1437,1438,
    1439,1440,1441,1442,1443,1444,1445,1446,1447,1448,1449,1450,1451,
    1452,1453,1454,1455,1456,1457,1458,1459,1460,1461,1462,1463,1464,
    1465,1466,1467,1468,1469,1470,1471,1472,1473,1474,1475,1476,1477,
    1478,1479,1480,1481,1482,1483,1484,1485,1486,1487,1488,1489,1490,
    1491,1492,1493,1494,1495,1496,1497,1498,1499,1500,1501,1502,1503,
    1504,1505,1506,1507,1508,1509,1510,1511,1512,1513,1514,1515,1516,
    1517,1518,1519,1520,1521,1522,1523,1524,1525,1526,1527,1528,1529,
    1530,1531,1532,1533,1534,1535,1536,1537,1538,1539,1540,1541,1542,
    1543,1544,1545,1546,1547,1548,1549,1550,1551,1552,1553,1554,1555,
    1556,1557,1558,1559,1560,1561,1562,1563,1564,1565,1566,1567,1568,
    1569,1570,1571,1572,1573,1574,1575,1576,1577,1578,1579,1580,1581,
    1582,1583,1584,1585,1586,1587,1588,1589,1590,1591,1592,1593,1594,
    1595,1596,1597,1598,1599,1600,1601,1602,1603,1604,1605,1606,1607,
    1608,1609,1610,1611,1612,1613,1614,1615,1616,1617,1618,1619,1620,
    1621,1622,1623,1624,1625,1626,1627,1628,1629,1630,1631,1632,1633,
    1634,1635,1636,1637,1638,1639,1640,1641,1642,1643,1644,1645,1646,
    1647,1648,1649,1650,1651,1652,1653,1654,1655,1656,1657,1658,1659,
    1660,1661,1662,1663,1664,1665,1666,1667,1668,1669,1670,1671,1672,
    1673,1674,1675,1676,1677,1678,1679,1680,1681,1682,1683,1684,1685,
    1686,1687,1688,1689,1690,1691,1692,1693,1694,1695,1696,1697,1698,
    1699,1700,1701,1702,1703,1704,1705,1706,1707,1708,1709,1710,1711,
    1712,1713,1714,1715,1716,1717,1718,1719,1720,1721,1722,1723,1724,
    3453,3454,3455,3456,3457,3458,3459,3460,3461,3462,3463,3464,3465,
    3466,3467,3468,3469,3470,3471,3472,3473,3474,3475,3476,3477,3478,
    3479,3480,3481,3482,3483,3484,3485,3486,3487,3488,3489,3490,3491,
    3492,3493,3494,3495,3496,3497,3498,3499,3500,3501,3502,3503,3504,
    3505,3506,3507,3508,3509,3510,3511,3512,3513,3514,3515,3516,3517,
    3518,3519,3520,3521,3522,3523,3524,3525,3526,3527,3528,3529,3530,
    3531,3532,3533,3534,3535,3536,3537,3538,3539,3540,3541,3542,3543,
    3544,3545,3546,3547,3548,3549,3550,3551,3552,3553,3554,3555,3556,
    3557,3558,3559,3560,3561,3562,3563,3564,3565,3566,
    541,542,543,544,545,546,547,548,549,550,551,552,553,554,555,
    556,557,558,559,560,561,562,563,564,565,566,567,568,569,570,
    820,821,822,823,824,825,826,827,828,829,830,831,832,833,834,
    835,836,837,838,839,840,841,842,843,844,845,846,847,848,
    849,850,851,
    1103,1104,1105,1106,1107,1108,1109,1110,1111,1112,1113,1114,
    1115,1116,1117,1118,1119,1120,1121,1122,1123,1124,1125,1126,
    1127,1128,1129,1130,1131,1132,1133,1134,1135,1136,1137,1138,
    1139,1140,1141,1142,1143,1144,1145,1146,1147,1148,1149,1150,
    1151,1152,1153,1154,1155,1156,1157,1158,1159,1160,1161,1162,
    1163,1164,1165,1166,1167,1168,1169,1170,1171,1172,1173,
]
for _i in _hw: A[_i] = 'Hardware & Embedded'
# Fix misassigned from hardware bulk
for _i in [541,542,543,544,545,546,547,548,549,550,551,552,553,554,555,
           556,557,558,559,560,561,562,563,564,565,566,567,568,569,570]:
    A[_i] = 'Data Science & Analytics'  # agriculture/biology research
for _i in [820,821,822,823,824,825,826,827,828,829,830,831,832,833,834,835,
           836,837,838,839,840,841,842,843,844,845,846,847,848,849,850,851]:
    A[_i] = 'Data Science & Analytics'  # math/statistics
A[820] = 'Data Science & Analytics'  # Actuarial
A[824] = 'Enterprise Tools & Platforms'  # Autodesk Revit
A[825] = 'Hardware & Embedded'  # Building Information Modeling
A[826] = 'Product & Design'  # Building Design
A[827] = 'Product & Design'  # Spatial Design
A[828] = 'Product & Design'  # Spatial Planning
A[829] = 'Hardware & Embedded'  # Carpentry
A[830] = 'Hardware & Embedded'  # Reinforced Concrete
A[831] = 'Hardware & Embedded'  # Masonry
A[832] = 'Hardware & Embedded'  # Concrete Mixing
A[833] = 'Business & Operations'  # Cost Estimation
A[834] = 'Legal & Compliance'  # Building Codes
A[835] = 'Databases & Data Engineering'  # Staging Area
A[836] = 'Business & Operations'  # Construction Management
A[837] = 'Hardware & Embedded'  # Renovation
A[838] = 'Hardware & Embedded'  # Composite Structures
A[839] = 'Hardware & Embedded'  # Painting
A[840] = 'Cloud & Infrastructure'  # Smart Grid
A[841] = 'Hardware & Embedded'  # Signaling (Crane Rigging)
A[842] = 'Hardware & Embedded'  # Insulator
A[843] = 'Hardware & Embedded'  # Trenching
A[844] = 'Industries'  # Construction → domain
A[845] = 'Hardware & Embedded'  # Green Building
A[846] = 'Hardware & Embedded'  # Thermal Insulation
A[847] = 'Product & Design'  # Furnishing
A[848] = 'Product & Design'  # Residential Design
A[849] = 'Business & Operations'  # Traffic Control
A[850] = 'Hardware & Embedded'  # Roofing
A[851] = 'Problem Solving & Critical Thinking'  # Task Analysis → soft

# Product & Design (technical)
for _i in [1103,1104,1105,1106,1107,1108,1109,1110,1111,1112,1113,1114,
           1115,1116,1117,1118,1119,1120,1121,1122,1123,1124,1125,1126,
           1127,1128,1129,1130,1131,1132,1133,1134,1135,1136,1137,1138,
           1139,1140,1141,1142,1143,1144,1145,1146,1147,1148,1149,1150,
           1151,1152,1153,1154,1155,1156,1157,1158,1159,1160,1161,1162,
           1163,1164,1165,1166,1167,1168,1169,1170,1171,1172,1173]:
    A[_i] = 'Product & Design'
A[1105] = 'Enterprise Tools & Platforms'  # Cinema 4D
A[1107] = 'Enterprise Tools & Platforms'  # Unity Engine
A[1116] = 'Enterprise Tools & Platforms'  # Unreal Engine
A[1117] = 'Backend & APIs'  # OpenGL
A[1118] = 'Enterprise Tools & Platforms'  # Game Engine
A[1152] = 'Product & Design'  # Graphic Communication
A[1153] = 'Data Science & Analytics'  # Visualization
A[1154] = 'Product & Design'  # 3D Computer Graphics
A[1157] = 'Product & Design'  # Computer Graphics
A[1158] = 'Enterprise Tools & Platforms'  # Adobe Spark
A[1159] = 'Enterprise Tools & Platforms'  # Adobe Illustrator
A[1164] = 'Enterprise Tools & Platforms'  # Adobe Photoshop
A[1165] = 'Enterprise Tools & Platforms'  # Autodesk Maya
A[1171] = 'Product & Design'  # Human Factors

# Enterprise Tools & Platforms
_ent = [
    2398,2399,2400,2401,2402,2403,2404,2405,2406,2407,2408,2409,2410,
    2411,2412,2413,2414,2415,2416,2417,2418,2419,2420,2421,2422,2423,
    2424,2425,2426,2427,2428,2429,
    2860,2861,2862,2863,2864,2865,2866,2867,2868,2869,2870,2871,2872,
    2873,2874,2875,2876,2877,2878,2879,
    2912,2913,2914,2915,2916,2917,2918,2919,2920,2921,2922,2923,2924,
    2925,2926,2927,2928,2929,2930,2931,2932,2933,2934,2935,2936,2937,
    2938,2939,
    3200,3201,3202,3203,3204,3205,3206,3207,3208,3209,3210,3211,3212,
    3213,3214,3215,3216,3217,3218,3219,3220,3221,3222,3223,3224,3225,
    952,1788,1789,525,3582,
]
for _i in _ent: A[_i] = 'Enterprise Tools & Platforms'
# Fix misassigned
A[2398] = 'DevOps & CI/CD'   # Agile Projects
A[2399] = 'DevOps & CI/CD'   # Sprint Backlogs
A[2400] = 'DevOps & CI/CD'   # Scrum (Software Development)
A[2401] = 'Databases & Data Engineering'  # Backlogs? No, Backlogs = backlog management → DevOps
A[2401] = 'DevOps & CI/CD'
A[2402] = 'DevOps & CI/CD'   # Pivotal Tracker
A[2403] = 'DevOps & CI/CD'   # Agile Leadership
A[2404] = 'DevOps & CI/CD'   # Continuous Integration
A[2405] = 'QA & Testing'     # TDD
A[2406] = 'DevOps & CI/CD'   # Agile Project Management
A[2407] = 'DevOps & CI/CD'   # Disciplined Agile
A[2408] = 'Security & Compliance'  # Nessus
A[2409] = 'Security & Compliance'  # Windows Defender
A[2410] = 'Databases & Data Engineering'  # Apache Hive
A[2411] = 'Databases & Data Engineering'  # Apache POI
A[2412] = 'DevOps & CI/CD'   # Apache Ant
A[2413] = 'Databases & Data Engineering'  # Apache Oozie
A[2414] = 'Frontend & Web'   # Apache Flex
A[2415] = 'Databases & Data Engineering'  # Apache Hadoop
A[2416] = 'Databases & Data Engineering'  # Apache Pig
A[2417] = 'Cloud & Infrastructure'  # Apache Mesos
A[2418] = 'Databases & Data Engineering'  # Apache Cassandra
A[2419] = 'Databases & Data Engineering'  # Apache HBase
A[2420] = 'Databases & Data Engineering'  # Apache Flink
A[2421] = 'Databases & Data Engineering'  # Apache Spark
A[2422] = 'Databases & Data Engineering'  # Spark Streaming
A[2423] = 'Backend & APIs'   # Java API for REST
A[2424] = 'Cloud & Infrastructure'  # API Gateway
A[2425] = 'Cloud & Infrastructure'  # Amazon API Gateway
A[2426] = 'Backend & APIs'   # RESTful API
A[2427] = 'Hardware & Embedded'  # Hardware Platform Interface
A[2428] = 'Backend & APIs'   # API
A[2429] = 'Databases & Data Engineering'  # JPA
A[2860] = 'Networking & Systems'  # Digital Transformation → Business? Keep tech: Cloud
A[2860] = 'Cloud & Infrastructure'
A[2862] = 'Enterprise Tools & Platforms'  # MIS
A[2864] = 'Security & Compliance'  # DRM
A[2865] = 'Enterprise Tools & Platforms'  # IT Service Management
A[2866] = 'Cloud & Infrastructure'  # Infrastructure Management
A[2867] = 'Business & Operations'  # Technology Roadmap
A[2868] = 'Business & Operations'  # Technology Life Cycle
A[2869] = 'Networking & Systems'  # User Information
A[2870] = 'Security & Compliance'  # IAM
A[2871] = 'Security & Compliance'  # SSO
A[2872] = 'Security & Compliance'  # Amazon Cognito
A[2873] = 'Security & Compliance'  # MFA (dup, already set)
A[2874] = 'Security & Compliance'  # Authorization
A[2875] = 'Security & Compliance'  # Azure Active Directory
A[2876] = 'Cloud & Infrastructure'  # Cloud9
A[2877] = 'Programming Languages'  # IDEs
A[2878] = 'Networking & Systems'  # Eclipse
A[2879] = 'Networking & Systems'  # Wearables
A[2912] = 'Enterprise Tools & Platforms'  # CICS
A[2913] = 'Backend & APIs'   # Entity Framework
A[2914] = 'Enterprise Tools & Platforms'  # Microsoft Power Platform
A[2915] = 'Backend & APIs'   # .NET Framework
A[2916] = 'Backend & APIs'   # ASP.NET MVC
A[2917] = 'Programming Languages'  # ADO.NET
A[2918] = 'Enterprise Tools & Platforms'  # Windows App Studio
A[2919] = 'Enterprise Tools & Platforms'  # Powerapps
A[2920] = 'Enterprise Tools & Platforms'  # DirectX
A[2921] = 'Enterprise Tools & Platforms'  # Microsoft Power Automate
A[2922] = 'Enterprise Tools & Platforms'  # Microsoft Visual Studio
A[2923] = 'Backend & APIs'   # Windows Communication Foundation
A[2924] = 'Enterprise Tools & Platforms'  # Universal Windows Platform
A[2925] = 'Enterprise Tools & Platforms'  # Microsoft Deployment Toolkit
A[2926] = 'Networking & Systems'  # Microsoft Windows SDK
A[2927] = 'Networking & Systems'  # Windows Vista
A[2928] = 'Networking & Systems'  # System Properties
A[2929] = 'Security & Compliance'  # BitLocker
A[2930] = 'Networking & Systems'  # Microsoft Windows
A[2931] = 'Networking & Systems'  # Proxy Servers
A[2932] = 'Networking & Systems'  # Data Distribution Services
A[2933] = 'Frontend & Web'   # Web Portals
A[2934] = 'Mobile'   # Mobile Application Development
A[2935] = 'Networking & Systems'  # Mobile Devices
A[2936] = 'Mobile'   # Google Play
A[2937] = 'Mobile'   # Rooting Android
A[2938] = 'Mobile'   # Android Studio
A[2939] = 'Mobile'   # Xamarin.Forms
A[3200] = 'Cloud & Infrastructure'  # Applications Architecture
A[3201] = 'Networking & Systems'  # Network Planning
A[3202] = 'Networking & Systems'  # Network Infrastructure
A[3203] = 'Cloud & Infrastructure'  # Software Systems
A[3204] = 'Data Science & Analytics'  # Systems Modeling
A[3205] = 'Cloud & Infrastructure'  # System Deployment
A[3206] = 'Hardware & Embedded'  # Digital Systems
A[3207] = 'Security & Compliance'  # User Accounts
A[3208] = 'Enterprise Tools & Platforms'  # Enterprise Messaging
A[3209] = 'Enterprise Tools & Platforms'  # MMC
A[3210] = 'Cloud & Infrastructure'  # Log Files
A[3211] = 'Networking & Systems'  # System Administration
A[3212] = 'Security & Compliance'  # Integrated Windows Auth
A[3213] = 'Security & Compliance'  # Email Filtering
A[3214] = 'Security & Compliance'  # Directory Service
A[3215] = 'Enterprise Tools & Platforms'  # Asset Tracking
A[3216] = 'Networking & Systems'  # Network Administration
A[3217] = 'Enterprise Tools & Platforms'  # HP Systems Insight
A[3218] = 'Cloud & Infrastructure'  # Failover
A[3219] = 'Cloud & Infrastructure'  # Nagios
A[3220] = 'DevOps & CI/CD'   # Change Tracking
A[3221] = 'Security & Compliance'  # ADFS
A[3222] = 'Security & Compliance'  # Identity Services Engine
A[3223] = 'Security & Compliance'  # Patch Management
A[3224] = 'Networking & Systems'  # UMTS
A[3225] = 'Networking & Systems'  # Data Transmissions
A[952]  = 'Enterprise Tools & Platforms'
A[1788] = 'Enterprise Tools & Platforms'
A[1789] = 'Enterprise Tools & Platforms'
A[525]  = 'Enterprise Tools & Platforms'
A[3582] = 'Enterprise Tools & Platforms'

# Frontend & Web
_fe = [
    3281,3282,3283,3284,3285,3286,3287,3288,3289,3290,3291,3292,3293,
    3294,3295,3296,3297,3298,3299,3300,3301,3302,3303,3304,3305,3306,
    3307,3308,3309,3310,3311,3312,3313,3314,3315,3316,3317,3318,3319,
    3320,3321,3322,3323,
    2903,2904,
    474,484,
]
for _i in _fe: A[_i] = 'Frontend & Web'
A[3281] = 'Product & Design'  # Intuitive Navigation
A[3282] = 'Frontend & Web'   # Mean Stack
A[3283] = 'Frontend & Web'   # Flexbox
A[3287] = 'Frontend & Web'   # CSS
A[3288] = 'Frontend & Web'   # Web Application Development
A[3289] = 'Frontend & Web'   # Bootstrap
A[3291] = 'Frontend & Web'   # Web Development
A[3296] = 'Frontend & Web'   # Web Pages
A[3299] = 'Frontend & Web'   # Web Accessibility Initiative
A[3303] = 'Frontend & Web'   # Character Encodings in HTML
A[3304] = 'Frontend & Web'   # Drag and Drop
A[3305] = 'Backend & APIs'   # Web Engineering
A[3308] = 'Frontend & Web'   # Single Page Application
A[3309] = 'Frontend & Web'   # HTML Components
A[3310] = 'Networking & Systems'  # Internet Services
A[3311] = 'Networking & Systems'  # Online Service Provider
A[3312] = 'Frontend & Web'   # Web Platforms
A[3313] = 'Frontend & Web'   # Web Tools
A[3314] = 'Cloud & Infrastructure'  # Internet Hosting Service
A[3315] = 'Cloud & Infrastructure'  # Amazon SQS
A[3316] = 'Backend & APIs'   # Web Services
A[3317] = 'Cloud & Infrastructure'  # AWS
A[3318] = 'Cloud & Infrastructure'  # Amazon Elasticsearch
A[3319] = 'Mobile'   # App Store iOS
A[3320] = 'Mobile'   # Apple Xcode
A[3321] = 'Mobile'   # Apple iOS
A[3322] = 'Mobile'   # Objective-C
A[3323] = 'Communication'   # ASL (this is in soft, but shows in tech—skip it's soft)
A[2903] = 'Frontend & Web'   # JavaScript Frameworks
A[2904] = 'Data Science & Analytics'  # D3.js
A[474] = 'Frontend & Web'   # Htmx
A[484] = 'Backend & APIs'   # Deno

# QA & Testing
_qa = [
    3056,3057,3058,3059,3060,3061,3062,3063,3064,3065,3066,3067,3068,
    3069,3070,3071,3072,3073,3074,3075,3076,3077,3078,3079,3080,3081,
    3082,3083,3084,3085,3086,3087,3088,3089,3090,3091,3092,3093,3094,
    3095,3096,3097,3098,3099,3100,3101,3102,3103,3104,3105,3106,3107,
    3108,3109,3110,3111,3112,3113,3114,3115,3116,3117,3118,3119,3120,
    3121,3122,3123,3124,3125,3126,3127,3128,3129,3130,3131,3132,3133,
    3134,3135,3136,3137,3138,3139,3140,3141,3142,3143,3144,3145,3146,
    3147,3148,3149,3150,3151,3152,3153,3154,3155,3156,3157,3158,3159,
    3160,3161,3162,3163,3164,3165,3166,3167,3168,3169,3170,3171,3172,
    3173,3174,3175,3176,3177,3178,3179,3180,3181,3182,3183,3184,3185,
    3186,3187,3188,3189,3190,3191,3192,3193,3194,3195,3196,3197,3198,
    3199,
]
for _i in _qa: A[_i] = 'QA & Testing'
A[3056] = 'Programming Languages'  # Programming Environments
A[3057] = 'Frontend & Web'   # Front End Design
A[3058] = 'Backend & APIs'   # Interactive Programming
A[3059] = 'Programming Languages'  # Structured Programming
A[3061] = 'Programming Languages'  # Programming Language Design
A[3062] = 'Programming Languages'  # Event-Driven Programming
A[3063] = 'Programming Languages'  # Code Sharing
A[3065] = 'Backend & APIs'   # SOA
A[3067] = 'Programming Languages'  # Generic Programming
A[3068] = 'Frontend & Web'   # Rich Internet Application
A[3069] = 'Backend & APIs'   # Multitier Architecture
A[3070] = 'Frontend & Web'   # Front End (Software Engineering)
A[3071] = 'Backend & APIs'   # Dependency Injection
A[3072] = 'Enterprise Tools & Platforms'  # Multiple Activation Key
A[3073] = 'DevOps & CI/CD'   # SDLC
A[3074] = 'Cloud & Infrastructure'  # Software Engineering
A[3075] = 'Backend & APIs'   # Adapters
A[3076] = 'Programming Languages'  # Program Flow
A[3077] = 'Programming Languages'  # Software Design Patterns
A[3078] = 'Programming Languages'  # Object-Oriented Modeling
A[3079] = 'Programming Languages'  # Procedural Programming
A[3080] = 'Programming Languages'  # OOP
A[3081] = 'Programming Languages'  # Functional Programming
A[3082] = 'Product & Design'  # Custom Software
A[3083] = 'Programming Languages'  # Console Applications
A[3084] = 'DevOps & CI/CD'   # Development Environment
A[3085] = 'DevOps & CI/CD'   # Software Release Life Cycle
A[3086] = 'Programming Languages'  # Software Construction
A[3087] = 'Programming Languages'  # LINQ
A[3088] = 'Programming Languages'  # State Machines
A[3089] = 'Cloud & Infrastructure'  # Reference Architecture
A[3090] = 'Cloud & Infrastructure'  # Scalability
A[3091] = 'Databases & Data Engineering'  # Information Model
A[3092] = 'Databases & Data Engineering'  # Nested Queries
A[3093] = 'Programming Languages'  # Software Modules
A[3094] = 'Programming Languages'  # Global Scope
A[3095] = 'DevOps & CI/CD'   # Open Source Technology
A[3096] = 'DevOps & CI/CD'   # Application Deployment
A[3097] = 'DevOps & CI/CD'   # Continuous Delivery
A[3098] = 'Hardware & Embedded'  # Device Drivers
A[3099] = 'DevOps & CI/CD'   # Open Standards
A[3100] = 'Backend & APIs'   # MVVM
A[3101] = 'Cloud & Infrastructure'  # Software Design
A[3102] = 'DevOps & CI/CD'   # DevOps
A[3103] = 'Backend & APIs'   # Full Stack Development
A[3104] = 'Backend & APIs'   # Application Development
A[3105] = 'Programming Languages'  # Immutability
A[3106] = 'Programming Languages'  # Class Diagram
A[3107] = 'Programming Languages'  # Code Reuse
A[3108] = 'Backend & APIs'   # Back End
A[3109] = 'Networking & Systems'  # POSIX
A[3110] = 'Hardware & Embedded'  # Microarchitecture
A[3111] = 'Security & Compliance'  # Cryptographic Hash
A[3112] = 'Databases & Data Engineering'  # Data Binding
A[3113] = 'Cloud & Infrastructure'  # Software Features
A[3114] = 'Cloud & Infrastructure'  # Software Development
A[3115] = 'Backend & APIs'   # MVC
A[3116] = 'Programming Languages'  # Resource Files
A[3117] = 'Programming Languages'  # Object-Oriented Design
A[3118] = 'Programming Languages'  # OOP Language
A[3119] = 'Cloud & Infrastructure'  # Scalability Design
A[3120] = 'DevOps & CI/CD'   # Process Driven Development
A[3121] = 'DevOps & CI/CD'   # Build Process
A[3122] = 'Data Science & Analytics'  # Priority Queue
A[3123] = 'Enterprise Tools & Platforms'  # Proprietary Software
A[3124] = 'Programming Languages'  # Codebase
A[3125] = 'DevOps & CI/CD'   # Code Review
A[3126] = 'Programming Languages'  # Managed Code
A[3127] = 'Programming Languages'  # Dynamic Programming
A[3128] = 'DevOps & CI/CD'   # Software Manufacturing
A[3129] = 'Databases & Data Engineering'  # Concurrency Controls
A[3130] = 'Cloud & Infrastructure'  # Software Architecture
A[3131] = 'Programming Languages'  # Exception Handling
A[3132] = 'Data Science & Analytics'  # Time Complexity
A[3133] = 'Backend & APIs'   # Service Development
A[3134] = 'QA & Testing'     # Debugging
A[3135] = 'Cloud & Infrastructure'  # Amazon ECR
A[3136] = 'Networking & Systems'  # LAMP
A[3137] = 'Networking & Systems'  # Grep
A[3138] = 'Security & Compliance'  # JSON Web Token
A[3139] = 'Frontend & Web'   # Angular CLI
A[3140] = 'Frontend & Web'   # WYSIWYG
A[3141] = 'Frontend & Web'   # WebAssembly
A[3142] = 'Hardware & Embedded'  # Kinect
A[3143] = 'Programming Languages'  # Code Editor
A[3144] = 'Cloud & Infrastructure'  # Docker (Software)
A[3145] = 'Data Science & Analytics'  # Qiskit
A[3146] = 'Security & Compliance'  # Disassembler
A[3147] = 'Networking & Systems'  # Emulators
A[3148] = 'Networking & Systems'  # RHEL
A[3149] = 'Frontend & Web'   # Windows Forms
A[3150] = 'Cloud & Infrastructure'  # AWS Elastic Beanstalk
A[3151] = 'Backend & APIs'   # Akka
A[3152] = 'Programming Languages'  # Code Snippets
A[3153] = 'Enterprise Tools & Platforms'  # Python Tools VS
A[3154] = 'Networking & Systems'  # cURL
A[3155] = 'Data Science & Analytics'  # Octave
A[3156] = 'DevOps & CI/CD'   # JBoss EAP
A[3157] = 'Databases & Data Engineering'  # Luigi
A[3158] = 'DevOps & CI/CD'   # JBoss Developer Studio
A[3159] = 'Frontend & Web'   # Document Object Model
A[3160] = 'DevOps & CI/CD'   # Toolchain
A[3161] = 'Cloud & Infrastructure'  # Open Platform
A[3162] = 'DevOps & CI/CD'   # Flux
A[3163] = 'Programming Languages'  # Programming Tools
A[3164] = 'QA & Testing'     # Risk-Based Testing
A[3165] = 'QA & Testing'     # Web Testing
A[3166] = 'QA & Testing'     # Software Quality
A[3167] = 'QA & Testing'     # Usability Testing
A[3168] = 'QA & Testing'     # Code Coverage
A[3169] = 'Cloud & Infrastructure'  # APM
A[3170] = 'QA & Testing'     # Development Testing
A[3171] = 'QA & Testing'     # Software Testing
A[3172] = 'QA & Testing'     # Verification and Validation
A[3173] = 'Enterprise Tools & Platforms'  # New Relic (SaaS) dup
A[3174] = 'QA & Testing'     # Exploratory Testing
A[3175] = 'Networking & Systems'  # Network Simulation
A[3176] = 'QA & Testing'     # UI Testing
A[3177] = 'QA & Testing'     # Junit4 (deactivated—skip)
A[3178] = 'QA & Testing'     # Boundary Testing
A[3179] = 'Cloud & Infrastructure'  # System Requirements
A[3180] = 'Networking & Systems'  # Network Analysis
A[3181] = 'AI & Machine Learning'  # Agent-Based Model
A[3182] = 'Cloud & Infrastructure'  # Systems Design (deactivated—skip)
A[3183] = 'Cloud & Infrastructure'  # Systems Integration
A[3184] = 'Cloud & Infrastructure'  # Systems Architecture
A[3185] = 'Cloud & Infrastructure'  # Data Centers
A[3186] = 'Programming Languages'  # Program Design Languages
A[3187] = 'Networking & Systems'  # Network Architecture
A[3188] = 'Data Science & Analytics'  # System Dynamics
A[3189] = 'Data Science & Analytics'  # Systems Theories
A[3190] = 'QA & Testing'     # System Testing
A[3191] = 'DevOps & CI/CD'   # Package Management
A[3192] = 'Networking & Systems'  # NFV
A[3193] = 'Networking & Systems'  # SDN
A[3194] = 'Cloud & Infrastructure'  # Requirements Elicitation
A[3195] = 'Cloud & Infrastructure'  # Systems Analysis
A[3196] = 'Hardware & Embedded'  # Command Controls
A[3197] = 'Data Science & Analytics'  # Conceptual Model
A[3198] = 'Networking & Systems'  # Network Config & Change Mgmt
A[3199] = 'Cloud & Infrastructure'  # Systems Engineering


def main():
    with app.app_context():
        now = __import__('datetime').datetime.utcnow()
        skills_by_id = {s.id: s for s in Skill.query.all()}
        recat_count = sub_count = 0

        # Step 1: recategorize
        for sid, (cat, sub) in RECAT.items():
            s = skills_by_id.get(sid)
            if not s or not s.is_verified: continue
            changed = False
            if s.category != cat:
                if APPLY: s.category = cat
                changed = True
            if s.subcategory != sub:
                if APPLY: s.subcategory = sub
                changed = True
            if changed:
                if APPLY: s.updated_at = now
                recat_count += 1

        # Step 2: subcategory assignments
        for sid, sub in A.items():
            s = skills_by_id.get(sid)
            if not s or not s.is_verified: continue
            if s.subcategory == sub: continue
            if APPLY:
                s.subcategory = sub
                s.updated_at = now
            sub_count += 1

        if APPLY:
            db.session.commit()
            print(f'✓ Committed. Recategorized: {recat_count}, Subcategories assigned: {sub_count}')
        else:
            print(f'Dry-run. Would recategorize: {recat_count}, assign subcategories: {sub_count}. Pass --apply.')


if __name__ == '__main__':
    main()
