# load aura csv data format

import csv
import numpy as np
import os
import math
import re

from . import imucal

d2r = math.pi / 180.0

# empty class we'll fill in with data members
# class Record: pass (deprecated)

def load(flight_dir, recalibrate=None):
    result = {}

    # load imu/gps data files
    event_file = os.path.join(flight_dir, "event-0.csv")
    imu_file = os.path.join(flight_dir, "imu-0.csv")
    imucal_json = os.path.join(flight_dir, "imucal.json")
    gps_file = os.path.join(flight_dir, "gps-0.csv")
    air_file = os.path.join(flight_dir, "air-0.csv")
    filter_file = os.path.join(flight_dir, "filter-0.csv")
    filter_post = os.path.join(flight_dir, "filter-post.csv")
    pilot_file = os.path.join(flight_dir, "pilot-0.csv")
    act_file = os.path.join(flight_dir, "act-0.csv")
    ap_file = os.path.join(flight_dir, "ap-0.csv")
    health_file = os.path.join(flight_dir, "health-0.csv")
    imu_bias_file = os.path.join(flight_dir, "imubias.csv")

    # HEY: in the latest aura code, calibrated magnetometer is logged,
    # not raw magnetometer, so we don't need to correct here.  We
    # could 'back correct' if we wanted original values for some
    # reason (using the calibration matrix saved with each flight
    # log.)
    
    # # vireo_01
    # mag_affine = np.array(
    #     [[ 1.6207467043,  0.0228992488,  0.0398638786,  0.1274248748],
    #      [-0.0169905025,  1.7164397411, -0.0001290047, -0.1140304977],
    #      [ 0.0424979948, -0.0038515935,  1.7193766423, -0.1449816095],
    #      [ 0.          ,  0.          ,  0.          ,  1.          ]]
    # )

    # telemaster apm2_101
    mag_affine = np.array(
        [[ 0.0026424919,  0.0001334248,  0.0000984977, -0.2235908546],
         [-0.000081925 ,  0.0026419229,  0.0000751835, -0.0010757621],
         [ 0.0000219407,  0.0000560341,  0.002541171 ,  0.040221458 ],
         [ 0.          ,  0.          ,  0.          ,  1.          ]]
    )
    
    # skywalker apm2_105
    # mag_affine = np.array(
    #      [[ 0.0025834778, 0.0001434776, 0.0001434961, -0.7900775707 ],
    #       [-0.0001903118, 0.0024796553, 0.0001365238,  0.1881142449 ],
    #       [ 0.0000556437, 0.0001329724, 0.0023791184,  0.1824851582, ],
    #       [ 0.0000000000, 0.0000000000, 0.0000000000,  1.0000000000  ]]
    # )

    #np.set_printoptions(precision=10,suppress=True)
    #print mag_affine

    pilot_mapping = 'Aura3'       # APM2 or Aura3
    result['event'] = []
    with open(event_file, 'r') as fevent:
        reader = csv.DictReader(fevent)
        for row in reader:
            event = {
                'time': float(row['timestamp']),
                'message': row['message']
            }
            if 'Aura3' in event['message']:
                pilot_mapping = 'Aura3'
            elif 'APM2' in event['message']:
                pilot_mapping = 'APM2'
            result['event'].append( event )

    result['imu'] = []
    with open(imu_file, 'r') as fimu:
        reader = csv.DictReader(fimu)
        for row in reader:
            imu = {
                'time': float(row['timestamp']),
                'p': float(row['p_rad_sec']),
                'q': float(row['q_rad_sec']),
                'r': float(row['r_rad_sec']),
                'ax': float(row['ax_mps_sec']),
                'ay': float(row['ay_mps_sec']),
                'az': float(row['az_mps_sec']),
                'hx': float(row['hx']),
                'hy': float(row['hy']),
                'hz': float(row['hz']),
                'temp': float(row['temp_C'])
            }
            result['imu'].append( imu )

    result['gps'] = []
    last_time = -1.0
    with open(gps_file, 'r') as fgps:
        reader = csv.DictReader(fgps)
        for row in reader:
            # Note: aurauas logs unix time of the gps record, not tow,
            # but for the purposes of the insgns algorithm, it's only
            # important to have a properly incrementing clock, it doesn't
            # really matter what the zero reference point of time is here.
            time = float(row['timestamp'])
            sats = int(row['satellites'])
            if sats >= 5 and time > last_time:
                gps = {
                    'time': time,
                    'unix_sec': float(row['unix_time_sec']),
                    'lat': float(row['latitude_deg']),
                    'lon': float(row['longitude_deg']),
                    'alt': float(row['altitude_m']),
                    'vn': float(row['vn_ms']),
                    've': float(row['ve_ms']),
                    'vd': float(row['vd_ms']),
                    'sats': sats
                }
                result['gps'].append(gps)
            last_time = time

    result['air'] = []
    with open(air_file, 'r') as fair:
        reader = csv.DictReader(fair)
        for row in reader:
            air = {
                'time': float(row['timestamp']),
                'static_press': float(row['pressure_mbar']),
                'diff_press': 0.0, # not directly available in aura flight log
                'temp': float(row['temp_C']),
                'airspeed': float(row['airspeed_smoothed_kt']),
                'alt_press': float(row['altitude_smoothed_m']),
                'alt_true': float(row['altitude_true_m']),
                'wind_dir': float(row['wind_dir_deg']),
                'wind_speed': float(row['wind_speed_kt'])
            }
            result['air'].append( air )

    # load filter records if they exist (for comparison purposes)
    result['filter'] = []
    with open(filter_file, 'r') as ffilter:
        reader = csv.DictReader(ffilter)
        for row in reader:
            lat = float(row['latitude_deg'])
            lon = float(row['longitude_deg'])
            psi_deg = float(row['heading_deg'])
            if psi_deg > 180.0:
                psi_deg = psi_deg - 360.0
            if psi_deg < -180.0:
                psi_deg = psi_deg + 360.0
            if abs(lat) > 0.0001 and abs(lon) > 0.0001:
                nav = {
                    'time': float(row['timestamp']),
                    'lat': lat*d2r,
                    'lon': lon*d2r,
                    'alt': float(row['altitude_m']),
                    'vn': float(row['vn_ms']),
                    've': float(row['ve_ms']),
                    'vd': float(row['vd_ms']),
                    'phi': float(row['roll_deg'])*d2r,
                    'the': float(row['pitch_deg'])*d2r,
                    'psi': psi_deg*d2r,
                    'p_bias': float(row['p_bias']),
                    'q_bias': float(row['q_bias']),
                    'r_bias': float(row['r_bias']),
                    'ax_bias': float(row['ax_bias']),
                    'ay_bias': float(row['ay_bias']),
                    'az_bias': float(row['az_bias'])
                }
                result['filter'].append(nav)

    # load filter (post process) records if they exist (for comparison
    # purposes)
    if os.path.exists(filter_post):
        result['filter_post'] = []
        with open(filter_post, 'r') as ffilter:
            reader = csv.DictReader(ffilter)
            for row in reader:
                lat = float(row['latitude_deg'])
                lon = float(row['longitude_deg'])
                psi_deg = float(row['heading_deg'])
                if psi_deg > 180.0:
                    psi_deg = psi_deg - 360.0
                if psi < -180.0:
                    psi_deg = psi_deg + 360.0
                if abs(lat) > 0.0001 and abs(lon) > 0.0001:
                    nav = {
                        'time': float(row['timestamp']),
                        'lat': lat*d2r,
                        'lon': lon*d2r,
                        'alt': float(row['altitude_m']),
                        'vn': float(row['vn_ms']),
                        've': float(row['ve_ms']),
                        'vd': float(row['vd_ms']),
                        'phi': float(row['roll_deg'])*d2r,
                        'the': float(row['pitch_deg'])*d2r,
                        'psi': psi_deg*d2r,
                        'p_bias': float(row['p_bias']),
                        'q_bias': float(row['q_bias']),
                        'r_bias': float(row['r_bias']),
                        'ax_bias': float(row['ax_bias']),
                        'ay_bias': float(row['ay_bias']),
                        'az_bias': float(row['az_bias'])
                    }
                    result['filter_post'].append(nav)

    if os.path.exists(pilot_file):
        print('Pilot input mapping:', pilot_mapping)
        result['pilot'] = []
        with open(pilot_file, 'r') as fpilot:
            reader = csv.DictReader(fpilot)
            for row in reader:
                if pilot_mapping == 'Aura3':
                    pilot = {
                        'time': float(row['timestamp']),
                        'auto_manual': float(row['channel[0]']),
                        'throttle_safety': float(row['channel[1]']),
                        'throttle': float(row['channel[2]']),
                        'aileron': float(row['channel[3]']),
                        'elevator': float(row['channel[4]']),
                        'rudder': float(row['channel[5]']),
                        'flaps': float(row['channel[6]']),
                        'aux1': float(row['channel[7]']),
                        'gear': 0
                    }
                elif pilot_mapping == 'APM2':
                    pilot = {
                        'time': float(row['timestamp']),
                        'aileron': float(row['channel[0]']),
                        'elevator': -float(row['channel[1]']),
                        'throttle': float(row['channel[2]']),
                        'rudder': float(row['channel[3]']),
                        'gear': float(row['channel[4]']),
                        'flaps': float(row['channel[5]']),
                        'aux1': float(row['channel[6]']),
                        'auto_manual': float(row['channel[7]']),
                        'throttle_safety': 0.0
                    }
                result['pilot'].append(pilot)

    if os.path.exists(act_file):
        result['act'] = []
        with open(act_file, 'r') as fact:
            reader = csv.DictReader(fact)
            for row in reader:
                act = {
                    'time': float(row['timestamp']),
                    'aileron': float(row['aileron_norm']),
                    'elevator': float(row['elevator_norm']),
                    'throttle': float(row['throttle_norm']),
                    'rudder': float(row['rudder_norm']),
                    'gear': float(row['channel5_norm']),
                    'flaps': float(row['flaps_norm']),
                    'aux1': float(row['channel7_norm']),
                    'auto_manual': float(row['channel8_norm'])
                }
                result['act'].append(act)

    if os.path.exists(ap_file):
        result['ap'] = []
        with open(ap_file, 'r') as fap:
            reader = csv.DictReader(fap)
            for row in reader:
                ap = {
                    'time': float(row['timestamp']),
                    'master_switch': int(row['master_switch']),
                    'pilot_pass_through': int(row['pilot_pass_through']),
                    'hdg': float(row['groundtrack_deg']),
                    'roll': float(row['roll_deg']),
                    'alt': float(row['altitude_msl_ft']),
                    'pitch': float(row['pitch_deg']),
                    'speed': float(row['airspeed_kt']),
                    'ground': float(row['altitude_ground_m'])
                }
                result['ap'].append(ap)

    if os.path.exists(health_file):
        result['health'] = []
        with open(health_file, 'r') as fhealth:
            reader = csv.DictReader(fhealth)
            for row in reader:
                health = {
                    'time': float(row['timestamp']),
                    'load_avg': float(row['system_load_avg'])
                }
                if 'avionics_vcc' in row:
                    health['avionics_vcc'] = float(row['avionics_vcc'])
                elif 'board_vcc' in row:
                    health['avionics_vcc'] = float(row['board_vcc'])
                if 'main_vcc' in row:
                    health['main_vcc'] = float(row['main_vcc'])
                elif 'extern_volts' in row:
                    health['main_vcc'] = float(row['extern_volts'])
                if 'cell_vcc' in row:
                    health['cell_vcc'] = float(row['cell_vcc'])
                elif 'extern_cell_volts' in row:
                    health['cell_vcc'] = float(row['extern_cell_volts'])
                if 'main_amps' in row:
                    health['main_amps'] = float(row['main_amps'])
                elif 'extern_amps' in row:
                    health['main_amps'] = float(row['extern_amps'])
                if 'total_mah' in row:
                    health['main_mah'] = float(row['total_mah'])
                elif 'extern_current_mah' in row:
                    health['main_mah'] = float(row['extern_current_mah'])
                result['health'].append(health)

    cal = imucal.Calibration()
    if os.path.exists(imucal_json):
        cal.load(imucal_json)
        print('back correcting imu data (to get original raw values)')
        cal.back_correct(result['imu'], result['filter'])

    if recalibrate:
        print('recalibrating imu data using alternate calibration file:', recalibrate)
        rcal = imucal.Calibration()
        rcal.load(recalibrate)
        result['imu'] = rcal.correct(result['imu'])

    return result

def save_filter_result(filename, data_store):
    keys = ['timestamp', 'latitude_deg', 'longitude_deg', 'altitude_m',
            'vn_ms', 've_ms', 'vd_ms', 'roll_deg', 'pitch_deg', 'heading_deg',
            'p_bias', 'q_bias', 'r_bias', 'ax_bias', 'ay_bias', 'az_bias',
            'status']
    with open(filename, 'w') as csvfile:
        writer = csv.DictWriter( csvfile, fieldnames=keys )
        writer.writeheader()
        size = len(data_store['nav'])
        for nav in data_store['nav']:
            row = dict()
            row['timestamp'] = '%.4f' % nav['time']
            row['latitude_deg'] = '%.10f' % (nav['lat']*180.0/math.pi)
            row['longitude_deg'] = '%.10f' % (nav['lon']*180.0/math.pi)
            row['altitude_m'] = '%.2f' % nav['alt']
            row['vn_ms'] = '%.4f' % nav['vn']
            row['ve_ms'] = '%.4f' % nav['ve']
            row['vd_ms'] = '%.4f' % nav['vd']
            row['roll_deg'] = '%.2f' % (nav['phi']*180.0/math.pi)
            row['pitch_deg'] = '%.2f' % (nav['the']*180.0/math.pi)
            row['heading_deg'] = '%.2f' % (nav['psi']*180.0/math.pi)
            row['p_bias'] = '%.4f' % nav['gbx']
            row['q_bias'] = '%.4f' % nav['gby']
            row['r_bias'] = '%.4f' % nav['gbz']
            row['ax_bias'] = '%.3f' % nav['abx']
            row['ay_bias'] = '%.3f' % nav['aby']
            row['az_bias'] = '%.3f' % nav['abz']
            row['status'] = '%d' % 0
            writer.writerow(row)
