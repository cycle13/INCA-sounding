#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 11 16:49:11 2020

@author: nal
"""
import pandas as pd
from metpy.interpolate import interpolate_1d
import xarray as xr
import numpy as np 
import datetime as dt
import math
import matplotlib.pyplot as plt
from metpy.interpolate import interpolate_1d
from scipy.signal import savgol_filter
from metpy import calc as cc
from metpy.units import units
from datetime import datetime, timedelta
import metpy.calc as mpcalc
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from scipy.interpolate import griddata

from dateutil.relativedelta import relativedelta
from metpy.calc import pressure_to_height_std

from numpy.lib.scimath import logn
from math import e
import metpy 

from matplotlib import cm
import matplotlib as mpl
from sympy import S, symbols, printing
    
def open_NUCAPS_file(NUCAPS_file):       
    ds = xr.open_dataset(NUCAPS_file, decode_times=False)  # time units are non-standard, so we dont decode them here 
    units, reference_date = ds.Time.attrs['units'].split(' since ')

    if units=='msec':
        ref_date = datetime.strptime(reference_date,"%Y-%m-%dT%H:%M:%SZ") # usually '1970-01-01T00:00:00Z'
        ds['datetime'] = [ -1 if np.isnan(t) else ref_date + timedelta(milliseconds=t) for t in ds.Time.data]
    return ds

def convert_H2O_MR_to_Td(H2O_MR, p):
    # input water vapour mass mixing ration in (mWV / mDA) kg/kg

    WVMR = H2O_MR * 1000 # convert to grams
    WVMR = WVMR * units('g/kg')
    e_1 = mpcalc.vapor_pressure(p_NUCAPS_orig, WVMR)
    T_d = mpcalc.dewpoint(e_1) 
    return T_d

def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return array[idx]

def calc_bias_temp(input_smoothed_INCA, RS_smoothed_INCA):
     diff_temp = np.subtract(input_smoothed_INCA.temperature_mean, RS_smoothed_INCA.temperature_mean, axis = 1)
     diff_temp = pd.DataFrame({'diff_temp':diff_temp.values, 'altitude_m': RS_smoothed_INCA.altitude_m.values})
     diff_temp_mean = diff_temp.groupby('altitude_m')['diff_temp'].mean().to_frame(name='mean_all').reset_index() 
     diff_temp_mean = pd.DataFrame({'diff_temp':diff_temp_mean.mean_all, 'altitude_m': diff_temp_mean.altitude_m})
     return diff_temp_mean
 
def calc_bias_temp_d(input_smoothed_INCA, RS_smoothed_INCA):       
     diff_temp_d = np.subtract(input_smoothed_INCA.temperature_d_mean, RS_smoothed_INCA.temperature_d_mean, axis = 1)
     diff_temp_d = pd.DataFrame({'diff_temp_d':diff_temp_d.values, 'altitude_m': RS_smoothed_INCA.altitude_m.values})
     diff_temp_d_mean = diff_temp_d.groupby('altitude_m')['diff_temp_d'].mean().to_frame(name='mean_all').reset_index()
     diff_temp_d_mean = pd.DataFrame({'diff_temp_d_mean':diff_temp_d_mean.mean_all, 'altitude_m': diff_temp_d_mean.altitude_m})  
     return diff_temp_d_mean
 
def calc_std_temp(input_data_smoothed_INCA, RS_data_smoothed_INCA):
    diff_temp = np.subtract(input_data_smoothed_INCA.temperature_mean, RS_data_smoothed_INCA.temperature_mean, axis = 1)
    diff_temp = pd.DataFrame({'diff_temp':diff_temp, 'altitude_mean': RS_data_smoothed_INCA.altitude_m})
        
    diff_temp_d = np.subtract(input_data_smoothed_INCA.temperature_d_mean, RS_data_smoothed_INCA.temperature_d_mean, axis = 1)
    diff_temp_d = pd.DataFrame({'diff_temp_d':diff_temp_d, 'altitude_m': RS_data_smoothed_INCA.altitude_m})
        
    diff_temp_ee = diff_temp.diff_temp
    diff_temp_ee_sqr = diff_temp_ee **2
        
    diff_temp_d_ee = diff_temp_d.diff_temp_d
    diff_temp_d_ee_sqr = diff_temp_d_ee **2
         
    altitude_diff = pd.DataFrame({'altitude_m' : input_data_smoothed_INCA.altitude_m, 'diff_temp_ee_sqr': diff_temp_ee_sqr, 'diff_temp_d_ee_sqr': diff_temp_d_ee_sqr})
        
    number_temp = altitude_diff.groupby(['altitude_m'])['diff_temp_ee_sqr'].count().to_frame(name='number').reset_index()
    number_temp[number_temp == 0] = np.nan
    number_temp_d = altitude_diff.groupby(['altitude_m'])['diff_temp_d_ee_sqr'].count().to_frame(name='number').reset_index()
    number_temp_d[number_temp_d == 0] = np.nan
        
    number = RA_data_filtered.groupby(['altitude_m']).count()
    diff_temp_sqr = altitude_diff.groupby(['altitude_m'])['diff_temp_ee_sqr'].sum()
    diff_temp_sqr = diff_temp_sqr.reset_index(drop=True)
    diff_temp_d_sqr = altitude_diff.groupby(['altitude_m'])['diff_temp_d_ee_sqr'].sum()
    diff_temp_d_sqr = diff_temp_d_sqr.reset_index(drop=True)
        
    std_temp = np.sqrt((diff_temp_sqr / (number_temp.number)))
    std_temp = pd.DataFrame({'std_temp': std_temp, 'altitude_m': number_temp.altitude_m})
    std_temp_d = np.sqrt((diff_temp_d_sqr / ( number_temp_d.number)))
    std_temp_d = pd.DataFrame({'std_temp_d': std_temp_d, 'altitude_m': number_temp.altitude_m})
        
    return std_temp, std_temp_d, number_temp, number_temp_d

def calc_std_temp_minbias(input_data_smoothed_INCA, RS_data_smoothed_INCA, bias_mean_NUCAPS_all_temp, bias_mean_NUCAPS_all_temp_d):   
    diff_temp = np.subtract(input_data_smoothed_INCA.temperature_mean, RS_data_smoothed_INCA.temperature_mean, axis = 1)
    diff_temp_1 = pd.DataFrame({'diff_temp':diff_temp, 'altitude_mean': RS_data_smoothed_INCA.altitude_m})
    diff_temp_1 = diff_temp_1[diff_temp_1.altitude_mean >= 490].reset_index(drop=True)
    alt_min = np.min(diff_temp_1.altitude_mean)
    nr_entr = int(len(diff_temp_1) / 43)
    bias_mean_NUCAPS_all_temp = bias_mean_NUCAPS_all_temp[bias_mean_NUCAPS_all_temp.altitude_m >=alt_min].reset_index(drop=True)
    bias_mean_NUCAPS_all_temp = pd.concat([bias_mean_NUCAPS_all_temp]*nr_entr).reset_index(drop=True) 
    diff_temp = np.subtract(diff_temp_1.diff_temp, bias_mean_NUCAPS_all_temp.diff_temp, axis = 1)
    diff_temp = pd.DataFrame({'diff_temp':diff_temp.values, 'altitude_mean': diff_temp_1.altitude_mean})
 
    diff_temp_d = np.subtract(input_data_smoothed_INCA.temperature_d_mean, RS_data_smoothed_INCA.temperature_d_mean, axis = 1)
    diff_temp_d_1 = pd.DataFrame({'diff_temp_d':diff_temp_d, 'altitude_mean': RS_data_smoothed_INCA.altitude_m})
    diff_temp_d_1 = diff_temp_d_1[diff_temp_d_1.altitude_mean >= 491].reset_index(drop=True)
    alt_min = np.min(diff_temp_d_1.altitude_mean)
    nr_entr = int(len(diff_temp_d_1) / 43)
    bias_mean_NUCAPS_all_temp_d = bias_mean_NUCAPS_all_temp_d[bias_mean_NUCAPS_all_temp_d.altitude_m >=alt_min].reset_index(drop=True)
    bias_mean_NUCAPS_all_temp_d = pd.concat([bias_mean_NUCAPS_all_temp_d]*nr_entr).reset_index(drop=True) 
    diff_temp_d = np.subtract(diff_temp_d_1.diff_temp_d, bias_mean_NUCAPS_all_temp_d.diff_temp_d_mean, axis = 1)
    diff_temp_d = pd.DataFrame({'diff_temp_d':diff_temp_d.values, 'altitude_mean': diff_temp_1.altitude_mean})
     
    diff_temp_ee = diff_temp.diff_temp
    diff_temp_ee_sqr = diff_temp_ee **2
        
    diff_temp_d_ee = diff_temp_d.diff_temp_d
    diff_temp_d_ee_sqr = diff_temp_d_ee **2
         
    altitude_diff = pd.DataFrame({'altitude_m' : diff_temp_1.altitude_mean, 'diff_temp_ee_sqr': diff_temp_ee_sqr, 'diff_temp_d_ee_sqr': diff_temp_d_ee_sqr})
        
    number_temp = altitude_diff.groupby(['altitude_m'])['diff_temp_ee_sqr'].count().to_frame(name='number').reset_index()
    number_temp[number_temp == 0] = np.nan
    number_temp_d = altitude_diff.groupby(['altitude_m'])['diff_temp_d_ee_sqr'].count().to_frame(name='number').reset_index()
    number_temp_d[number_temp_d == 0] = np.nan
        
    number = RA_data_filtered.groupby(['altitude_m']).count()
    diff_temp_sqr = altitude_diff.groupby(['altitude_m'])['diff_temp_ee_sqr'].sum()
    diff_temp_sqr = diff_temp_sqr.reset_index(drop=True)
    diff_temp_d_sqr = altitude_diff.groupby(['altitude_m'])['diff_temp_d_ee_sqr'].sum()
    diff_temp_d_sqr = diff_temp_d_sqr.reset_index(drop=True)
        
    std_temp = np.sqrt((diff_temp_sqr / (number_temp.number)))
    std_temp = pd.DataFrame({'std_temp': std_temp, 'altitude_m': number_temp.altitude_m})
    std_temp_d = np.sqrt((diff_temp_d_sqr / ( number_temp_d.number)))
    std_temp_d = pd.DataFrame({'std_temp_d': std_temp_d, 'altitude_m': number_temp.altitude_m})
    
    return std_temp, std_temp_d, number_temp, number_temp_d

def interpolate_to_INCA_grid(firstobj, lastobj, INCA_grid, input_data_filtered): # interpolation of all data

    INCA_grid = INCA_grid.HHL[::-1]
    INCA_grid = INCA_grid.reset_index(drop=True)
    input_grid_smoothed_all = pd.DataFrame()
    while firstobj != lastobj:
        nowdate = firstobj.strftime('%Y%m%d')
        #print(nowdate) 
        input_data_time = input_data_filtered[input_data_filtered.time_YMDHMS == firstobj]
        input_data_time = input_data_time.reset_index(drop=True)
        if input_data_time.empty:
            firstobj = firstobj + dt.timedelta(days=1)
        else:  
            input_data = input_data_time.altitude_m.reset_index(drop=True)
            input_temp = input_data_time.temperature_degC.reset_index(drop=True)
            input_temp_d = input_data_time.dew_point_degC.reset_index(drop=True)
            input_temperature_interp = pd.DataFrame({'temperature_degC' : griddata(input_data.values, input_temp.values, INCA_grid.values)})
            input_temperature_d_interp = pd.DataFrame({'temperature_d_degC' : griddata(input_data.values, input_temp_d.values, INCA_grid.values)})
            input_interp = pd.DataFrame({'altitude_mean':INCA_grid, 'temperature_degC': input_temperature_interp.temperature_degC, 'temperature_d_degC' : input_temperature_d_interp.temperature_d_degC})
    
            input_grid_smoothed_all = input_grid_smoothed_all.append(input_interp)
            
            firstobj= firstobj + dt.timedelta(days=1) 


def interpolate_RS_to_INCA_grid(firstobj, lastobj, INCA_grid, input_data_filtered, comparison_grid): # interpolation of only selected data
    INCA_grid = INCA_grid.HHL[::-1]
    INCA_grid = INCA_grid.reset_index(drop=True)
    input_grid_smoothed_all = pd.DataFrame()
    while firstobj != lastobj:
        nowdate = firstobj.strftime('%Y%m%d')
        #print(nowdate) 
        input_data_time = input_data_filtered[input_data_filtered.time_YMDHMS == firstobj]
        input_data_time = input_data_time.reset_index(drop=True)
        comparison_grid_time = comparison_grid[comparison_grid.time_YMDHMS == firstobj]
        comparison_grid_time = comparison_grid_time.reset_index(drop=True)   
  
        if comparison_grid_time.empty:
            firstobj = firstobj + dt.timedelta(days=1)
            #print('now')
            
        else:  
            altitude_min = min(comparison_grid_time.altitude_m)
            altitude_max = max(comparison_grid_time.altitude_m)
            
            INCA_grid_min = find_nearest(INCA_grid, altitude_min)
            INCA_grid_max = find_nearest(INCA_grid, altitude_max)
            
            INCA_grid_lim = INCA_grid[(INCA_grid <= INCA_grid_max) & (INCA_grid >= INCA_grid_min)]
            INCA_grid_lim = INCA_grid_lim.reset_index(drop=True)
            
            input_data = input_data_time.altitude_m.reset_index(drop=True)
            input_temp = input_data_time.temperature_degC.reset_index(drop=True)
            input_temp_d = input_data_time.dew_point_degC.reset_index(drop=True)
            
            #input_temp_unc = input_data_time.uncertainty_temperature_K.reset_index(drop=True)
            #input_temp_d_unc = input_data_time.uncertainty_dew_point_K.reset_index(drop=True)
            
            input_temperature_interp = pd.DataFrame({'temperature_mean' : griddata(input_data.values, input_temp.values, INCA_grid_lim.values)})
            input_temperature_d_interp = pd.DataFrame({'temperature_d_mean' : griddata(input_data.values, input_temp_d.values, INCA_grid_lim.values)})
            #input_temperature_uncertainty = pd.DataFrame({'temperature_d_mean' : griddata(input_data.values, input_temp_unc.values, INCA_grid_lim.values)})
            #input_temperature_d_uncertainty = pd.DataFrame({'temperature_d_mean' : griddata(input_data.values, input_temp_d_unc.values, INCA_grid_lim.values)})

            input_interp = pd.DataFrame({'altitude_m':INCA_grid_lim, 'temperature_mean': input_temperature_interp.temperature_mean, 'temperature_d_mean' : input_temperature_d_interp.temperature_d_mean})
    
            input_grid_smoothed_all = input_grid_smoothed_all.append(input_interp)
            
            firstobj= firstobj + dt.timedelta(days=1) 
    return input_grid_smoothed_all
                                              
##################################################### define time ####################################################### 
firstdate = '2019050112000'
lastdate = '2020050112000'
firstobj=dt.datetime.strptime(firstdate,'%Y%m%d%H%M%S')
lastobj=dt.datetime.strptime(lastdate,'%Y%m%d%H%M%S')

### !! daytime ### (midnight: 0000, noon: 1200)
daytime = 'noon' # alternatively 'noon' possible
if daytime == 'midnight':
   DT = 0
   DT_NUCAPS = 23
else:
   DT = 12
   DT_NUCAPS = 11
   
bias_temp_all = pd.DataFrame()
bias_temp_d_all = pd.DataFrame()
        
std_temp_all = pd.DataFrame() 
std_temp_d_all = pd.DataFrame()

DELTA = 100
#lastobj_month = firstobj + relativedelta(months=1) # split into month

for j in range(0, 1000, DELTA): # time -120, 60
    print(j)
    lastobj_month = lastobj # the whole year
    ##################################################################### define paths and read data ##################################################################
    
    ## read data
    RS_archive   = '/data/COALITION2/PicturesSatellite/results_NAL/Radiosondes/Payerne/'
    RA_archive   = '/data/COALITION2/PicturesSatellite/results_NAL/RALMO/Payerne/'
    SMN_archive = '/data/COALITION2/PicturesSatellite/results_NAL/SwissMetNet/Payerne'
    NUCAPS_archive = '/data/COALITION2/PicturesSatellite/results_NAL/NUCAPS'
    INCA_archive = '/data/COALITION2/PicturesSatellite/results_NAL'
    MEAN_PROFILES_archive = '/data/COALITION2/PicturesSatellite/results_NAL/Plots/mean_profiles'
    BIAS_archive = '/data/COALITION2/PicturesSatellite/results_NAL/Plots/bias'
    STD_archive = '/data/COALITION2/PicturesSatellite/results_NAL/Plots/std'
    
    ## read data
    RS_data = xr.open_dataset(RS_archive+'/RS_concat.nc').to_dataframe()
    RA_data = xr.open_dataset(RA_archive+'/RA_concat_wp').to_dataframe()
    SMN_data = xr.open_dataset(SMN_archive+'/SMN_concat1.nc').to_dataframe()
    NUCAPS_data = open_NUCAPS_file(NUCAPS_archive+'/NUCAPS_Payerne_-60min_0min_3500km.nc')
    INCA_grid = pd.read_csv(INCA_archive+'/INCA_grid.csv') 
    
    INCA_grid = pd.read_csv('/data/COALITION2/PicturesSatellite/results_NAL/INCA_grid.csv') 
    bias_mean_NUCAPS_all_temp = pd.read_csv('/data/COALITION2/PicturesSatellite/results_NAL/NUCAPS/bias_mean_NUCAPS_all_temp.csv') 
    bias_mean_NUCAPS_all_temp_d = pd.read_csv('/data/COALITION2/PicturesSatellite/results_NAL/NUCAPS/bias_mean_NUCAPS_all_temp_d.csv') 
    
    INCA_grid = pd.read_csv('/data/COALITION2/PicturesSatellite/results_NAL/INCA_grid.csv') 
    ### NUCAPS ###
    p_NUCAPS = NUCAPS_data.Pressure.values
    p_NUCAPS = pd.DataFrame({'pressure_hPa': (np.tile(p_NUCAPS, 730))})
    p_NUCAPS_1 = p_NUCAPS['pressure_hPa'].values * units.hPa
 
    T_NUCAPS = NUCAPS_data.Temperature.values -273.15
    T_NUCAPS = pd.DataFrame({'temperature_degC' : np.reshape(T_NUCAPS, (T_NUCAPS.shape[0] * T_NUCAPS.shape[1]))})
    T_NUCAPS_1 = (NUCAPS_data.Temperature.values -273.15) * units.degC
    
    H2O_MR = np.reshape(NUCAPS_data['H2O_MR'].values,(T_NUCAPS.shape[0] * T_NUCAPS.shape[1])) * units('g/kg')
    H2O_MR_1 = NUCAPS_data['H2O_MR'].values
    H2O_MR = pd.DataFrame({'mixing_ratio' : H2O_MR})
 
    p_NUCAPS_2 = NUCAPS_data.Pressure.values * units.hPa
    WVMR = (H2O_MR_1 * 1000) * units('g/kg')
    e_1 = mpcalc.vapor_pressure(p_NUCAPS_2, WVMR)
    T_d = mpcalc.dewpoint(e_1) 
    T_d_NUCAPS = pd.DataFrame({'dew_point_degC' : np.reshape(T_d, (T_NUCAPS.shape[0] * T_NUCAPS.shape[1]))}) 
        
    datetime_NUCAPS = NUCAPS_data.datetime.values
    datetime_NUCAPS = pd.DataFrame({'time_YMDHMS_1': (np.repeat(datetime_NUCAPS, 100))})
            
    datetime_NUCAPS_round = pd.DataFrame(datetime_NUCAPS.time_YMDHMS_1.dt.ceil('60 min').values, columns = ['time_YMDHMS'])
    datetime_NUCAPS_round.time_YMDHMS[datetime_NUCAPS_round.time_YMDHMS.dt.hour == 1] = datetime_NUCAPS_round.time_YMDHMS - dt.timedelta(hours=1)
    datetime_NUCAPS_round.time_YMDHMS[datetime_NUCAPS_round.time_YMDHMS.dt.hour == 13] = datetime_NUCAPS_round.time_YMDHMS - dt.timedelta(hours=1)
        
    quality_flag = NUCAPS_data.Quality_Flag.values
    quality_flag = pd.DataFrame({'quality_flag' : (np.repeat(quality_flag, 100))})
        
    surf_pres = NUCAPS_data.Surface_Pressure.values
    surf_pres = pd.DataFrame({'surf_pres': (np.repeat(surf_pres, 100))})
        
    topography = NUCAPS_data.Topography.values
    topography = pd.DataFrame({'topography' : (np.repeat(topography, 100))})
        
    skin_temp = NUCAPS_data.Skin_Temperature
    skin_temp = pd.DataFrame({'skin_temp' : (np.repeat(skin_temp, 100))})
        
    dist = NUCAPS_data.distance.values
    dist = pd.DataFrame({'dist' : (np.repeat(dist, 100))})

    NUCAPS_time_diff = pd.DataFrame({'time_diff' : (((datetime_NUCAPS.time_YMDHMS_1 - datetime_NUCAPS_round.time_YMDHMS).dt.total_seconds())/ 60)})
       
    NUCAPS_data = pd.concat([p_NUCAPS, T_NUCAPS, T_d_NUCAPS, dist, datetime_NUCAPS, datetime_NUCAPS_round, NUCAPS_time_diff, skin_temp, quality_flag, H2O_MR, surf_pres, topography], axis = 1)
    NUCAPS_data = NUCAPS_data.dropna()  
    
    NUCAPS_data = NUCAPS_data[(NUCAPS_data.dist >= j) & (NUCAPS_data.dist <= j+DELTA)]
    
    #NUCAPS_data = NUCAPS_data[(NUCAPS_data.time >= j) & (NUCAPS_data.time <= j+DELTA)] # filter time 
    
    ###################################################### add relevant variables ##############################################
    ##### RALMO #####
    # relevant variables for raman lidar are pressure, temperature in degC, dewpoint temperature and relative hum
    ## add temperature in degC
    temp_K = RA_data.temperature_K - 273.15
    RA_data.insert(value=temp_K,column = "temperature_degC", loc=10)
    RA_data['temperature_degC'][RA_data['temperature_K']== int(10000000)] = np.nan
    RA_data['uncertainty_temperature_K'][RA_data['temperature_K']==int(1000000)] = np.nan
        
    ## add dewpoint temperature
    dewpoint_degC = cc.dewpoint_from_specific_humidity(RA_data['specific_humidity_gkg-1'].values * units('g/kg'), (RA_data.temperature_K.values) * units.kelvin, RA_data.pressure_hPa.values * units.hPa)
    RA_data.insert(value=dewpoint_degC,column = "dew_point_degC", loc=11)
    RA_data['dew_point_degC'][RA_data['specific_humidity_gkg-1']== int(10000000)] = np.nan
        
    ## add dewpoint temperature uncertainty 
    RA_data['uncertainty_specific_humidity_gkg-1'][RA_data['uncertainty_specific_humidity_gkg-1']== int(10000000)] = np.nan
    dewpoint_degC_uncertainty = cc.dewpoint_from_specific_humidity((RA_data['uncertainty_specific_humidity_gkg-1'].values * units('g/kg')), (RA_data.temperature_K.values) * units.kelvin, RA_data.pressure_hPa.values * units.hPa)
    #dewpoint_degC_uncertainty = cc.dewpoint_from_specific_humidity((RA_data['uncertainty_specific_humidity_gkg-1'].values + RA_data['specific_humidity_gkg-1'].values)  * units('g/kg'), (RA_data.temperature_K.values) * units.kelvin, RA_data.pressure_hPa.values * units.hPa)
    #dewpoint_degC_uncertainty = dewpoint_degC_uncertainty - dewpoint_degC
        
    RA_data.insert(value=dewpoint_degC_uncertainty,column = "uncertainty_dew_point_K", loc=11)
    
    ## add relative humidity
    RH_percent = cc.relative_humidity_from_specific_humidity(RA_data['specific_humidity_gkg-1'].values * units('g/kg'), (RA_data.temperature_K.values +273.15) * units.kelvin, RA_data.pressure_hPa.values * units.hPa)
    RA_data.insert(value=temp_K,column = "relative_humidity_percent", loc=12) 
     
    ## change time format
    RA_data['time_YMDHMS'] = pd.to_datetime(RA_data.time_YMDHMS, format = '%Y%m%d%H%M%S')
    RS_data['time_YMDHMS'] = pd.to_datetime(RS_data.time_YMDHMS, format = '%Y%m%d%H%M%S')
    SMN_data['time_YMDHMS'] = pd.to_datetime(SMN_data.time_YMDHMS, format = '%Y%m%d%H%M%S')
    
    #print(firstobj.strftime('%Y%m%d%H%M%S')) 
    
    #######################################################filter #########################################################
    ## filter time 
    RS_data_filtered = RS_data[(RS_data['time_YMDHMS'] >= firstobj) & (RS_data['time_YMDHMS'] < lastobj_month)] 
    RA_data_filtered = RA_data[(RA_data['time_YMDHMS'] >= firstobj) & (RA_data['time_YMDHMS'] < lastobj_month)]
    NUCAPS_data_filtered = NUCAPS_data[(NUCAPS_data['time_YMDHMS'] >= firstobj) & (NUCAPS_data['time_YMDHMS'] < lastobj_month)]
        
    ## filter noon or midnight
    RS_data_filtered = RS_data_filtered[RS_data_filtered['time_YMDHMS'].dt.hour == DT]
    RS_data_filtered = RS_data_filtered.reset_index()
        
    RA_data_filtered = RA_data_filtered[RA_data_filtered['time_YMDHMS'].dt.hour == DT]
    RA_data_filtered = RA_data_filtered.reset_index()
    
    NUCAPS_data_filtered = NUCAPS_data_filtered[(NUCAPS_data_filtered['time_YMDHMS'].dt.hour == DT)]
    NUCAPS_data_filtered = NUCAPS_data_filtered.reset_index()
    
    if NUCAPS_data_filtered.empty:
        print('empty')
        diff_temp_mean_NUCAPS_all = pd.DataFrame({'diff_temp': np.nan, 'altitude_m': np.nan, 'distance_interval_min' : j, 'distance_interval_max' : j + 1000}, index = [0])
        diff_temp_d_mean_NUCAPS_all = pd.DataFrame({'diff_temp_d': np.nan, 'altitude_m': np.nan, 'distance_interval_min' : j, 'distance_interval_max' : j + 1000}, index = [0])
        std_temp_mean_NUCAPS_all = pd.DataFrame({'std_temp': np.nan, 'altitude_m': np.nan, 'distance_interval_min' : j, 'distance_interval_max' : j + 1000}, index = [0])
        std_temp_d_mean_NUCAPS_all = pd.DataFrame({'std_temp_d': np.nan, 'altitude_m': np.nan, 'distance_interval_min' : j, 'distance_interval_max' : j + 1000}, index = [0])
            
    else:  
        NUCAPS_data_filtered['altitude_m'] = 0
        print('else')
        RS_data_filtered = RS_data_filtered[RS_data_filtered.temperature_degC != 10000000.0]
        RS_data_filtered = RS_data_filtered.rename(columns={'geopotential_altitude_m' : 'altitude_m'})
             
        ####################################################### Add altitude ######################################################### 

        firstobj_NUCAPS = firstobj
    
        NUCAPS_data_filtered['altitude_m'] = 0
           
        altitude_m  = pd.DataFrame()   
        while firstobj_NUCAPS != lastobj_month:
            nowdate = firstobj_NUCAPS.strftime('%Y%m%d')
            NUCAPS_data_time = NUCAPS_data_filtered[(NUCAPS_data_filtered['time_YMDHMS'] == firstobj_NUCAPS)]
            NUCAPS_data_time = NUCAPS_data_time.reset_index(drop=True)
            NUCAPS_data_time['altitude_m'] = '0'
            
            SMN_data_time = SMN_data[(SMN_data['time_YMDHMS'] == firstobj_NUCAPS)]
            
            RS_data_time = RS_data[(RS_data['time_YMDHMS'] == firstobj_NUCAPS)]
            
            if NUCAPS_data_time.empty:
                firstobj_NUCAPS = firstobj_NUCAPS + dt.timedelta(days=1)
                #print('nope')
                
            else:  
                #print(nowdate)
                data_comma_temp = NUCAPS_data_time[['time_YMDHMS', 'pressure_hPa', 'temperature_degC', 'altitude_m', 'skin_temp', 'surf_pres', 'topography']]
                data_comma_temp = data_comma_temp.append({'time_YMDHMS' : NUCAPS_data_time.time_YMDHMS[0], 'pressure_hPa' : NUCAPS_data_time.surf_pres.iloc[0],  'temperature_degC': NUCAPS_data_time.skin_temp.iloc[0] - 273.15, 'altitude_m' : NUCAPS_data_time.topography[0]}, ignore_index=True)
                #data_comma_temp = data_comma_temp.append({'time_YMDHMS' : SMN_data_time.time_YMDHMS[0], 'pressure_hPa' : SMN_data_time.pressure_hPa[0],  'temperature_degC': SMN_data_time.temperature_degC[0], 'altitude_m' :491}, ignore_index=True)
                #data_comma_temp = data_comma_temp.append({'time_YMDHMS' : RS_data_time.time_YMDHMS[0], 'pressure_hPa' : RS_data_time.pressure_hPa[1],  'temperature_degC': RS_data_time.temperature_degC[1], 'altitude_m' : RS_data_time.geopotential_altitude_m[1]}, ignore_index=True)
                data_comma_temp = data_comma_temp[::-1].reset_index(drop=True)
                
                for i in range(1,len(data_comma_temp)):
                    p_profile = (data_comma_temp.pressure_hPa.iloc[i-1], data_comma_temp.pressure_hPa.iloc[i]) * units.hPa
                    t_profile = (data_comma_temp.temperature_degC.iloc[i-1], data_comma_temp.temperature_degC.iloc[i]) * units.degC
                    deltax = metpy.calc.thickness_hydrostatic(p_profile, t_profile)
                    data_comma_temp.altitude_m[i] = data_comma_temp.altitude_m.iloc[i-1] + (deltax.magnitude)
                
              
                altitude_m_1 = pd.DataFrame(data_comma_temp.altitude_m[1:])
                altitude_m = altitude_m.append(altitude_m_1[::-1])
                firstobj_NUCAPS = firstobj_NUCAPS + dt.timedelta(days=1)     
                                             
        NUCAPS_data_filtered.altitude_m = altitude_m.values
        NUCAPS_data_all = NUCAPS_data_filtered
            
        ####################################################### interpolation to INCA grid and mean #######################################################
        ### RADIOSONDE ###
        ## RS - ORIGINAL
        #RS_original_mean_temp = RS_data_filtered.groupby(['altitude_m'])['temperature_degC'].mean().to_frame(name='mean_all').reset_index()
        #RS_original_mean_temp_d = RS_data_filtered.groupby(['altitude_m'])['dew_point_degC'].mean().to_frame(name='mean_all').reset_index()
        
        # smoothing with all times
        #RS_smoothed_all = interpolate_to_INCA_grid(firstobj, lastobj, INCA_grid, RS_data_filtered)
        #RS_smoothed_all_mean_temp =  RS_smoothed_all.groupby('altitude_mean')['temperature_degC'].mean().to_frame(name='mean_all').reset_index()
        #RS_smoothed_all_mean_temp_d =  RS_smoothed_all.groupby('altitude_mean')['temperature_d_degC'].mean().to_frame(name='mean_all').reset_index()
        
        ### RALMO ###
        # smoothing with selected values
        #RS_smoothed_RA = interpolate_RS_to_INCA_grid(firstobj, lastobj, INCA_grid, RS_data_filtered, RA_data_filtered)
        #RS_smoothed_RA_mean_temp = RS_smoothed_RA.groupby('altitude_m')['temperature_mean'].mean().to_frame(name='mean_all').reset_index()
        #RS_smoothed_RA_mean_temp_d = RS_smoothed_RA.groupby('altitude_m')['temperature_d_mean'].mean().to_frame(name='mean_all').reset_index()
            
        #RA_smoothed_INCA = interpolate_RS_to_INCA_grid(firstobj, lastobj, INCA_grid, RA_data_filtered, RA_data_filtered)
        #RA_smoothed_INCA_mean_temp = RA_smoothed_INCA.groupby('altitude_m')['temperature_mean'].mean().to_frame(name='mean_all').reset_index()
        #RA_smoothed_INCA_mean_temp_d = RA_smoothed_INCA.groupby('altitude_m')['temperature_d_mean'].mean().to_frame(name='mean_all').reset_index()
        
        ## RA uncertainty 
        #RA_mean_temp_uncertainty = RA_smoothed_INCA.groupby(['altitude_m'])['temperature_mean_unc'].mean().to_frame(name='mean_all').reset_index()
        #RA_mean_temp_d_uncertainty = RA_smoothed_INCA.groupby(['altitude_m'])['temperature_d_mean_unc'].mean().to_frame(name='mean_all').reset_index()
    
        ## specific humidity
        #RA_data_filtered_x = RA_data_filtered
        #RA_data_filtered_x = RA_data_filtered_x[RA_data_filtered_x['specific_humidity_gkg-1'] != 1e+07]
        #spec_hum_mean = RA_data_filtered_x.groupby(['altitude_m'])['specific_humidity_gkg-1'].mean().to_frame(name='mean_all').reset_index()
            
        ### NUCAPS ###
        ## all
        RS_smoothed_NUCAPS_all = interpolate_RS_to_INCA_grid(firstobj, lastobj_month, INCA_grid, RS_data_filtered, NUCAPS_data_all)
        RS_smoothed_NUCAPS_mean_temp_all = RS_smoothed_NUCAPS_all.groupby('altitude_m')['temperature_mean'].mean().to_frame(name='mean_all').reset_index()
        RS_smoothed_NUCAPS_mean_temp_d_all = RS_smoothed_NUCAPS_all.groupby('altitude_m')['temperature_d_mean'].mean().to_frame(name='mean_all').reset_index()
        
        NUCAPS_smoothed_INCA_all = interpolate_RS_to_INCA_grid(firstobj, lastobj_month, INCA_grid, NUCAPS_data_all, NUCAPS_data_all)
        NUCAPS_smoothed_INCA_all = NUCAPS_smoothed_INCA_all.astype(float)
        NUCAPS_smoothed_INCA_mean_temp_all = NUCAPS_smoothed_INCA_all.groupby('altitude_m')['temperature_mean'].mean().to_frame(name='mean_all').reset_index()
        NUCAPS_smoothed_INCA_mean_temp_d_all = NUCAPS_smoothed_INCA_all.groupby('altitude_m')['temperature_d_mean'].mean().to_frame(name='mean_all').reset_index()
            
        #NUCAPS_data_filtered.altitude_m = NUCAPS_data_filtered.altitude_m.round()
        #fx = NUCAPS_round.groupby('altitude_m')['temperature_degC'].mean().to_frame(name='mean_all').resetn_index()
        #plt.plot(fx.mean_all, fx.altitude_m, color = 'blue')
        #plt.plot(RS_original_mean_temp.mean_all, RS_original_mean_temp.altitude_m, color = 'orange')
                              
        ####################################################### bias and std #######################################################
        # RALMO - NUCAPS all
        diff_temp_mean_NUCAPS_all = calc_bias_temp(NUCAPS_smoothed_INCA_all, RS_smoothed_NUCAPS_all)
        diff_temp_mean_NUCAPS_all['distance_interval_middle'] = j + DELTA/2
        diff_temp_d_mean_NUCAPS_all = calc_bias_temp_d(NUCAPS_smoothed_INCA_all, RS_smoothed_NUCAPS_all)
        diff_temp_d_mean_NUCAPS_all['distance_interval_middle'] = j + DELTA/2
        
        ### std ###
        # RALMO - NUCAPS all
        std_temp_NUCAPS_all, std_temp_d_NUCAPS_all, number_temp_NUCAPS_all, number_temp_d_NUCAPS_all = calc_std_temp_minbias(NUCAPS_smoothed_INCA_all, RS_smoothed_NUCAPS_all, bias_mean_NUCAPS_all_temp, bias_mean_NUCAPS_all_temp_d)
        #std_temp_NUCAPS_all, std_temp_d_NUCAPS_all, number_temp_NUCAPS_all, number_temp_d_NUCAPS_all = calc_std_temp(NUCAPS_smoothed_INCA_all, RS_smoothed_NUCAPS_all)

        std_temp_NUCAPS_all['distance_interval_middle'] = j + DELTA/2
        std_temp_d_NUCAPS_all['distance_interval_middle'] = j + DELTA/2
                  
        bias_temp_all  = bias_temp_all.append(diff_temp_mean_NUCAPS_all)   
        bias_temp_d_all = bias_temp_d_all.append(diff_temp_d_mean_NUCAPS_all)
                
        std_temp_all = std_temp_all.append(std_temp_NUCAPS_all)  
        std_temp_d_all = std_temp_d_all.append(std_temp_d_NUCAPS_all)
     

       
bias_temp_all_mean = bias_temp_all.groupby('distance_interval_middle')['diff_temp'].mean().to_frame(name='mean_all').reset_index()
std_temp_all_mean = std_temp_all.groupby('distance_interval_middle')['std_temp'].mean().to_frame(name='mean_all').reset_index()
bias_temp_d_all_mean = bias_temp_d_all.groupby('distance_interval_middle')['diff_temp_d_mean'].mean().to_frame(name='mean_all').reset_index()
std_temp_d_all_mean = std_temp_d_all.groupby('distance_interval_middle')['std_temp_d'].mean().to_frame(name='mean_all').reset_index()

bias_temp_all_LT = bias_temp_all[bias_temp_all.altitude_m <= 2000]
bias_temp_all_mean_LT = bias_temp_all_LT.groupby('distance_interval_middle')['diff_temp'].mean().to_frame(name='mean_all').reset_index()
bias_temp_d_all_LT = bias_temp_d_all[bias_temp_all.altitude_m <= 2000]
bias_temp_d_all_mean_LT = bias_temp_d_all_LT.groupby('distance_interval_middle')['diff_temp_d_mean'].mean().to_frame(name='mean_all').reset_index()

std_temp_all_LT = std_temp_all[std_temp_all.altitude_m <= 2000]
std_temp_all_mean_LT = std_temp_all_LT.groupby('distance_interval_middle')['std_temp'].mean().to_frame(name='mean_all').reset_index()
std_temp_d_all_LT = std_temp_d_all[std_temp_d_all.altitude_m <= 2000]
std_temp_d_all_mean_LT = std_temp_d_all_LT.groupby('distance_interval_middle')['std_temp_d'].mean().to_frame(name='mean_all').reset_index()

bias_temp_all_MT = bias_temp_all[(bias_temp_all.altitude_m > 2000) & (bias_temp_all.altitude_m < 8000)]
bias_temp_all_mean_MT = bias_temp_all_MT.groupby('distance_interval_middle')['diff_temp'].mean().to_frame(name='mean_all').reset_index()
bias_temp_d_all_MT = bias_temp_d_all[(bias_temp_all.altitude_m > 2000) & (bias_temp_all.altitude_m < 8000)]
bias_temp_d_all_mean_MT = bias_temp_d_all_MT.groupby('distance_interval_middle')['diff_temp_d_mean'].mean().to_frame(name='mean_all').reset_index()

std_temp_all_MT = std_temp_all[(std_temp_all.altitude_m > 2000) & (std_temp_all.altitude_m < 8000)]
std_temp_all_mean_MT = std_temp_all_MT.groupby('distance_interval_middle')['std_temp'].mean().to_frame(name='mean_all').reset_index()
std_temp_d_all_MT = std_temp_d_all[(std_temp_d_all.altitude_m > 2000) & (std_temp_all.altitude_m < 8000)]
std_temp_d_all_mean_MT = std_temp_d_all_MT.groupby('distance_interval_middle')['std_temp_d'].mean().to_frame(name='mean_all').reset_index()

bias_temp_all_UT = bias_temp_all[bias_temp_all.altitude_m >= 8000]
bias_temp_all_mean_UT = bias_temp_all_UT.groupby('distance_interval_middle')['diff_temp'].mean().to_frame(name='mean_all').reset_index()
bias_temp_d_all_UT = bias_temp_d_all[bias_temp_all.altitude_m >= 8000]
bias_temp_d_all_mean_UT = bias_temp_d_all_UT.groupby('distance_interval_middle')['diff_temp_d_mean'].mean().to_frame(name='mean_all').reset_index()

std_temp_all_UT = std_temp_all[std_temp_all.altitude_m >= 8000]
std_temp_all_mean_UT = std_temp_all_UT.groupby('distance_interval_middle')['std_temp'].mean().to_frame(name='mean_all').reset_index()
std_temp_d_all_UT = std_temp_d_all[std_temp_d_all.altitude_m >= 8000]
std_temp_d_all_mean_UT = std_temp_d_all_UT.groupby('distance_interval_middle')['std_temp_d'].mean().to_frame(name='mean_all').reset_index()



trend = np.polyfit(bias_temp_all_mean.distance_interval_middle, bias_temp_all_mean.mean_all,1)
trend1 = np.polyfit(std_temp_all_mean.distance_interval_middle, std_temp_all_mean.mean_all,1)
trend_std = np.polyfit(bias_temp_d_all_mean.distance_interval_middle, bias_temp_d_all_mean.mean_all,1)
trend1_std = np.polyfit(std_temp_d_all_mean.distance_interval_middle, std_temp_d_all_mean.mean_all,1)
trendpoly = np.poly1d(trend) 
trendpoly1 = np.poly1d(trend1)
trendpoly_std = np.poly1d(trend_std) 
trendpoly1_std = np.poly1d(trend1_std)

trend = np.polyfit(bias_temp_all_mean_LT.distance_interval_middle, bias_temp_all_mean_LT.mean_all,1)
trend1 = np.polyfit(std_temp_all_mean_LT.distance_interval_middle, std_temp_all_mean_LT.mean_all,1)
trend_std = np.polyfit(bias_temp_d_all_mean_LT.distance_interval_middle, bias_temp_d_all_mean_LT.mean_all,1)
trend1_std = np.polyfit(std_temp_d_all_mean_LT.distance_interval_middle, std_temp_d_all_mean_LT.mean_all,1)
trendpoly_LT = np.poly1d(trend) 
trendpoly1_LT = np.poly1d(trend1)
trendpoly_std_LT = np.poly1d(trend_std) 
trendpoly1_std_LT = np.poly1d(trend1_std)

trend = np.polyfit(bias_temp_all_mean_MT.distance_interval_middle, bias_temp_all_mean_MT.mean_all,1)
trend1 = np.polyfit(std_temp_all_mean.distance_interval_middle, std_temp_all_mean.mean_all,1)
trend_std = np.polyfit(bias_temp_d_all_mean_MT.distance_interval_middle, bias_temp_d_all_mean_MT.mean_all,1)
trend1_std = np.polyfit(std_temp_d_all_mean_MT.distance_interval_middle, std_temp_d_all_mean_MT.mean_all,1)
trendpoly_MT = np.poly1d(trend) 
trendpoly1_MT = np.poly1d(trend1)
trendpoly_std_MT = np.poly1d(trend_std) 
trendpoly1_std_MT = np.poly1d(trend1_std)

trend = np.polyfit(bias_temp_all_mean_UT.distance_interval_middle, bias_temp_all_mean_UT.mean_all,1)
trend1 = np.polyfit(std_temp_all_mean_UT.distance_interval_middle, std_temp_all_mean_UT.mean_all,1)
trend_std = np.polyfit(bias_temp_d_all_mean_UT.distance_interval_middle, bias_temp_d_all_mean_UT.mean_all,1)
trend1_std = np.polyfit(std_temp_d_all_mean_UT.distance_interval_middle, std_temp_d_all_mean_UT.mean_all,1)
trendpoly_UT = np.poly1d(trend) 
trendpoly1_UT = np.poly1d(trend1)
trendpoly_std_UT = np.poly1d(trend_std) 
trendpoly1_std_UT = np.poly1d(trend1_std)


# bias 
fig = plt.figure(figsize = (25,8))
ax1 = fig.add_axes([0.5,0.1,0.5,0.8])

bias_temp_all.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='diff_temp',  ax = ax1,  colormap = cm.coolwarm, legend=False)
ax1.plot(bias_temp_all_mean.distance_interval_middle, bias_temp_all_mean.mean_all, color='goldenrod', linewidth = 3, zorder = 100)
ax1.scatter(bias_temp_all_mean.distance_interval_middle, bias_temp_all_mean.mean_all, color='gold', s = 50, zorder = 1000)
ax1.plot(bias_temp_all_mean.distance_interval_middle, trendpoly(bias_temp_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000)

#bias_temp_all_LT.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='diff_temp',  ax = ax1,  colormap = cm.coolwarm, legend=False)
#ax1.plot(bias_temp_all_mean_LT.distance_interval_middle, bias_temp_all_mean_LT.mean_all, color='goldenrod', linewidth = 3)
#ax1.scatter(bias_temp_all_mean_LT.distance_interval_middle, bias_temp_all_mean_LT.mean_all, color='gold', s = 50, zorder = 100)
#ax1.plot(bias_temp_all_mean.distance_interval_middle, trendpoly_LT(bias_temp_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000)

#bias_temp_all_MT.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='diff_temp',  ax = ax1,  colormap = cm.seismic, legend=False)
#ax1.plot(bias_temp_all_mean_MT.distance_interval_middle, bias_temp_all_mean_MT.mean_all, color='goldenrod', linewidth = 3)
#ax1.scatter(bias_temp_all_mean_MT.distance_interval_middle, bias_temp_all_mean_MT.mean_all, color='gold', s = 50, zorder = 100)
#ax1.plot(bias_temp_all_mean.distance_interval_middle, trendpoly_MT(bias_temp_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000, label="${}$".format(eq_latex))

#bias_temp_all_UT.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='diff_temp',  ax = ax1,  colormap = cm.GnBu_r, legend=False)
#ax1.plot(bias_temp_all_mean_UT.distance_interval_middle, bias_temp_all_mean_UT.mean_all, color='goldenrod', linewidth = 3)
#ax1.scatter(bias_temp_all_mean_UT.distance_interval_middle, bias_temp_all_mean_UT.mean_all, color='gold', s = 50, zorder = 100)
#ax1.plot(bias_temp_all_mean.distance_interval_middle, trendpoly_UT(bias_temp_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000)

ax1.hlines(0, 0, 1005, linestyle = '--', color = 'black')
ax1.set_xlim(0,1005)
#ax1.plot(bias_temp_d_all.diff_temp_d_mean, bias_temp_d_all.diff_temp_d, color = 'darkslategrey', linewidth = 2, label = 'Td', linestyle = '--', zorder = 1)
ax1.axhspan(-2, 2, alpha=0.5, color='grey', zorder = 0)
ax1.set_ylabel('bias [K]', fontsize = 30)
ax1.set_xlabel('distance [km]', fontsize = 30)
ax1.tick_params(labelsize = 30)
ax1.set_title('Bias', fontsize = 30)


     
# std 
fig = plt.figure(figsize = (25,8))
ax1 = fig.add_axes([0.5,0.1,0.5,0.8])
#std_temp_all.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='std_temp',  ax = ax1,  colormap = cm.seismic, legend=False)
#ax1.plot(std_temp_all_mean.distance_interval_middle, std_temp_all_mean.mean_all, color='goldenrod', linewidth = 3, zorder = 100)
#ax1.scatter(std_temp_all_mean.distance_interval_middle, std_temp_all_mean.mean_all, color='gold', s = 50, zorder = 1000)
#ax1.plot(std_temp_all_mean.distance_interval_middle, trendpoly1(std_temp_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000)

std_temp_d_all.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='std_temp_d',  ax = ax1,  colormap = cm.seismic, legend=False)
ax1.plot(std_temp_d_all_mean.distance_interval_middle, std_temp_d_all_mean.mean_all, color='goldenrod', linewidth = 3, zorder = 100)
ax1.scatter(std_temp_d_all_mean.distance_interval_middle, std_temp_d_all_mean.mean_all, color='gold', s = 50, zorder = 1000)
ax1.plot(std_temp_all_mean.distance_interval_middle, trendpoly1_std(std_temp_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000)


#std_temp_all_LT.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='std_temp',  ax = ax1,  colormap = cm.coolwarm, legend=False)
#ax1.plot(std_temp_all_mean_LT.distance_interval_middle, std_temp_all_mean_LT.mean_all, color='goldenrod', linewidth = 3)
#ax1.scatter(std_temp_all_mean_LT.distance_interval_middle, std_temp_all_mean_LT.mean_all, color='gold', s = 50, zorder = 100)
#ax1.plot(std_temp_all_mean.distance_interval_middle, trendpoly1_LT(std_temp_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000)

#std_temp_d_all_LT.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='std_temp',  ax = ax1,  colormap = cm.coolwarm, legend=False)
#ax1.plot(std_temp_d_all_mean_LT.distance_interval_middle, std_temp_d_all_mean_LT.mean_all, color='goldenrod', linewidth = 3)
#ax1.scatter(std_temp_d_all_mean_LT.distance_interval_middle, std_temp_d_all_mean_LT.mean_all, color='gold', s = 50, zorder = 100)
#ax1.plot(std_temp_d_all_mean.distance_interval_middle, trendpoly1_LT(std_temp_d_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000)



#std_temp_all_MT.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='std_temp',  ax = ax1,  colormap = cm.seismic, legend=False)
#ax1.plot(std_temp_all_mean_MT.distance_interval_middle, std_temp_all_mean_MT.mean_all, color='goldenrod', linewidth = 3)
#ax1.scatter(std_temp_all_mean_MT.distance_interval_middle, std_temp_all_mean_MT.mean_all, color='gold', s = 50, zorder = 100)
#ax1.plot(std_temp_all_mean.distance_interval_middle, trendpoly1_MT(std_temp_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000, label="${}$".format(eq_latex))

#std_temp_d_all_MT.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='std_temp_d',  ax = ax1,  colormap = cm.seismic, legend=False)
#ax1.plot(std_temp_d_all_mean_MT.distance_interval_middle, std_temp_d_all_mean_MT.mean_all, color='goldenrod', linewidth = 3)
#ax1.scatter(std_temp_d_all_mean_MT.distance_interval_middle, std_temp_d_all_mean_MT.mean_all, color='gold', s = 50, zorder = 100)
#ax1.plot(std_temp_d_all_mean.distance_interval_middle, trendpoly1_std_MT(std_temp_d_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000, label="${}$".format(eq_latex))


#std_temp_all_UT.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='std_temp',  ax = ax1,  colormap = cm.GnBu_r, legend=False)
#ax1.plot(std_temp_all_mean_UT.distance_interval_middle, std_temp_all_mean_UT.mean_all, color='goldenrod', linewidth = 3)
#ax1.scatter(std_temp_all_mean_UT.distance_interval_middle, std_temp_all_mean_UT.mean_all, color='gold', s = 50, zorder = 100)
#ax1.plot(std_temp_all_mean.distance_interval_middle, trendpoly1_UT(std_temp_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000)

#std_temp_d_all_UT.groupby('altitude_m').plot(kind = 'line', x = 'distance_interval_middle',   y ='std_temp',  ax = ax1,  colormap = cm.GnBu_r, legend=False)
#ax1.plot(std_temp_d_all_mean_UT.distance_interval_middle, std_temp_d_all_mean_UT.mean_all, color='goldenrod', linewidth = 3)
#ax1.scatter(std_temp_d_all_mean_UT.distance_interval_middle, std_temp_d_all_mean_UT.mean_all, color='gold', s = 50, zorder = 100)
#ax1.plot(std_temp_d_all_mean.distance_interval_middle, trendpoly1_UT(std_temp_d_all_mean.distance_interval_middle), color = 'red', linewidth = 3, zorder = 10000)

plt.legend('')
#ax1.hlines(0, 0, 1005, linestyle = '--', color = 'black')
#ax1.set_xlim(0,1005)
#ax1.plot(bias_temp_d_all.diff_temp_d_mean, bias_temp_d_all.diff_temp_d, color = 'darkslategrey', linewidth = 2, label = 'Td', linestyle = '--', zorder = 1)
ax1.axhspan(-2, 2, alpha=0.5, color='grey', zorder = 0)
ax1.set_ylabel('std', fontsize = 30)
ax1.set_xlabel('distance [km]', fontsize = 30)
ax1.tick_params(labelsize = 30)
ax1.set_title('Std', fontsize = 30)
ax1.grid()
ax1.set_ylim(0, 20)
ax1.set_yticks(np.arange(0, 20, 5))
ax1.set_xlim(0,1000)
ax1.set_xticks(np.arange(0,1000,100))

fig.savefig('/data/COALITION2/PicturesSatellite/results_NAL/Plots/std/NUCAPS/distance/DIST_STD_TEMP_min', dpi=300, bbox_inches = "tight")










 