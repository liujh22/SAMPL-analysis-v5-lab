'''
plot correlation of features by time
1. corr of angular vel at each timpoint with preBoutPitch / atkAngle / trajectory deviation
2. corr of ins. trajectory at each timepoint with bout trajectory
trajectory deviation (trajecgtory residual) is defined as (bout_trajecgtory - pitch_pre_bout)

'''

#%%
# import sys
import os,glob
from pickle import FRAME
import pandas as pd
from plot_functions.plt_tools import round_half_up 
import numpy as np # numpy
import seaborn as sns
import matplotlib.pyplot as plt
from scipy import stats
from astropy.stats import jackknife_resampling

from plot_functions.get_data_dir import (get_data_dir, get_figure_dir)
from plot_functions.get_index import get_index
from plot_functions.plt_tools import (set_font_type, defaultPlotting, distribution_binned_average, day_night_split)
from plot_functions.get_bout_kinetics import get_set_point
from tqdm import tqdm
import matplotlib as mpl
from scipy.signal import savgol_filter

set_font_type()

# %%
def corr_calc(df, grp_cols, col1, col2, name):
    corr_calc = df.groupby(grp_cols).apply(
            lambda y: stats.pearsonr(
                y[col1].values,y[col2].values)[0]
                )
    corr_calc.name = name
    output = corr_calc.to_frame()
    return output
# %%
# Paste root directory here
# if_plot_by_speed = True
pick_data = '7dd_all'
if_jackknife = 0




root, FRAME_RATE= get_data_dir(pick_data)

folder_name = f'BT4_disassociate_fin_body'
folder_dir = get_figure_dir(pick_data)
fig_dir = os.path.join(folder_dir, folder_name)

try:
    os.makedirs(fig_dir)
    print(f'fig folder created:{folder_name}')
except:
    print('Notes: re-writing old figures')
    
peak_idx , total_aligned = get_index(FRAME_RATE)
idxRANGE = [peak_idx-round_half_up(0.30*FRAME_RATE),peak_idx+round_half_up(0.22*FRAME_RATE)]
spd_bins = np.arange(5,25,4)

# %% features for plotting
all_features = [
    'propBoutAligned_speed', 
    'propBoutAligned_accel',    # angular accel calculated using raw angular vel
    'linear_accel', 
    'propBoutAligned_pitch', 
    'propBoutAligned_angVel',   # smoothed angular velocity
    'propBoutInflAligned_accel',
    'propBoutAligned_instHeading', 
    # 'heading_sub_pitch',
            # 'propBoutAligned_x',
            # 'propBoutAligned_y', 
            # 'propBoutInflAligned_angVel',
            # 'propBoutInflAligned_speed', 
            # 'propBoutAligned_angVel_hDn',
            # # 'propBoutAligned_speed_hDn', 
            # 'propBoutAligned_pitch_hDn',
            # # 'propBoutAligned_angVel_flat', 
            # # 'propBoutAligned_speed_flat',
            # # 'propBoutAligned_pitch_flat', 
            # 'propBoutAligned_angVel_hUp',
            # 'propBoutAligned_speed_hUp', 
            # 'propBoutAligned_pitch_hUp', 
    'ang_speed',
    'ang_accel_of_SMangVel',    # angular accel calculated using smoothed angVel
    # 'xvel', 'yvel',

]

# %%
# CONSTANTS
# %%
T_INITIAL = -0.25 #s
T_PREP_200 = -0.2
T_PREP_150 = -0.15
T_PRE_BOUT = -0.10 #s
T_POST_BOUT = 0.1 #s
T_post_150 = 0.15
T_END = 0.2
T_MID_ACCEL = -0.05
T_MID_DECEL = 0.05


idx_initial = round_half_up(peak_idx + T_INITIAL * FRAME_RATE)
idx_pre_bout = round_half_up(peak_idx + T_PRE_BOUT * FRAME_RATE)
idx_post_bout = round_half_up(peak_idx + T_POST_BOUT * FRAME_RATE)
idx_mid_accel = round_half_up(peak_idx + T_MID_ACCEL * FRAME_RATE)
idx_mid_decel = round_half_up(peak_idx + T_MID_DECEL * FRAME_RATE)
idx_end = round_half_up(peak_idx + T_END * FRAME_RATE)

idx_dur250ms = round_half_up(250/1000*FRAME_RATE)
idx_dur275ms = round_half_up(275/1000*FRAME_RATE)
# %%
all_conditions = []
folder_paths = []
# get the name of all folders under root
for folder in os.listdir(root):
    if folder[0] != '.':
        folder_paths.append(root+'/'+folder)
        all_conditions.append(folder)

all_around_peak_data = pd.DataFrame()
all_cond0 = []
all_cond0 = []

# go through each condition folders under the root
for condition_idx, folder in enumerate(folder_paths):
    # enter each condition folder (e.g. 7dd_ctrl)
    for subpath, subdir_list, subfile_list in os.walk(folder):
        # if folder is not empty
        if subdir_list:
            # reset for each condition
            around_peak_data = pd.DataFrame()
            # loop through each sub-folder (experiment) under each condition
            for expNum, exp in enumerate(subdir_list):
                # angular velocity (angVel) calculation
                rows = []
                # for each sub-folder, get the path
                exp_path = os.path.join(subpath, exp)
                # get pitch                
                exp_data = pd.read_hdf(f"{exp_path}/bout_data.h5", key='prop_bout_aligned')#.loc[:,['propBoutAligned_angVel','propBoutAligned_speed','propBoutAligned_accel','propBoutAligned_heading','propBoutAligned_pitch']]
                exp_data = exp_data.assign(ang_speed=exp_data['propBoutAligned_angVel'].abs(),
                                            yvel = exp_data['propBoutAligned_y'].diff()*FRAME_RATE,
                                            xvel = exp_data['propBoutAligned_x'].diff()*FRAME_RATE,
                                            # linear_accel = exp_data['propBoutAligned_speed'].diff(),
                                            ang_accel = exp_data['propBoutAligned_angVel'].diff(),
                                            tsp = exp_data['propBoutAligned_instHeading'] - exp_data['propBoutAligned_pitch']
                                           )
                # assign frame number, total_aligned frames per bout
                exp_data = exp_data.assign(idx=round_half_up(len(exp_data)/total_aligned)*list(range(0,total_aligned)))
                
                # - get the index of the rows in exp_data to keep (for each bout, there are range(0:51) frames. keep range(20:41) frames)
                bout_time = pd.read_hdf(f"{exp_path}/bout_data.h5", key='prop_bout2').loc[:,['aligned_time']]
                # for i in bout_time.index:
                # # if only need day or night bouts:
                for i in day_night_split(bout_time,'aligned_time').index:
                    rows.extend(list(range(i*total_aligned+idxRANGE[0],i*total_aligned+idxRANGE[1])))
                exp_data = exp_data.assign(expNum = expNum,
                                           exp_id = condition_idx*100+expNum)
                around_peak_data = pd.concat([around_peak_data,exp_data.loc[rows,:]])
    # combine data from different conditions
    cond1 = all_conditions[condition_idx].split("_")[0]
    all_cond0.append(cond1)
    cond1 = all_conditions[condition_idx].split("_")[1]
    all_cond0.append(cond1)
    all_around_peak_data = pd.concat([all_around_peak_data, around_peak_data.assign(dpf=cond1,
                                                                                            cond1=cond1)])
all_around_peak_data = all_around_peak_data.assign(
    time_ms = (all_around_peak_data['idx']-peak_idx)/FRAME_RATE*1000,
)

# %% tidy data
all_cond0 = list(set(all_cond0))
all_cond0.sort()
all_cond0 = list(set(all_cond0))
all_cond0.sort()

all_around_peak_data = all_around_peak_data.reset_index(drop=True)
peak_speed = all_around_peak_data.loc[all_around_peak_data.idx==peak_idx,'propBoutAligned_speed'],

grp = all_around_peak_data.groupby(np.arange(len(all_around_peak_data))//(idxRANGE[1]-idxRANGE[0]))
all_around_peak_data = all_around_peak_data.assign(
    peak_speed = np.repeat(peak_speed,(idxRANGE[1]-idxRANGE[0])),
    bout_number = grp.ngroup(),
                                )
all_around_peak_data = all_around_peak_data.assign(
                                    speed_bin = pd.cut(all_around_peak_data['peak_speed'],spd_bins,labels = np.arange(len(spd_bins)-1))
                                )
# %%
# smooth data?
# cols_to_smooth = ['propBoutAligned_pitch','propBoutAligned_instHeading']
# for col_to_smooth in cols_to_smooth:
#     all_around_peak_data[col_to_smooth] = savgol_filter(all_around_peak_data[col_to_smooth],3,2)
# %%
# cal bout features
corr_all = pd.DataFrame()
corr_bySpd = pd.DataFrame()
features_all = pd.DataFrame()
expNum = all_around_peak_data['expNum'].max()
jackknife_idx = jackknife_resampling(np.array(list(range(expNum+1))))


if if_jackknife == 1:
    idx_list = jackknife_idx
else:
    idx_list = np.array(list(range(expNum+1)))
    idx_list = [[item] for item in idx_list]
    
for excluded_exp, idx_group in enumerate(idx_list):
    group = all_around_peak_data.query('expNum in @idx_group')
    yy = (group.loc[group['idx']==idx_post_bout,'propBoutAligned_y'].values - group.loc[group['idx']==idx_pre_bout,'propBoutAligned_y'].values)
    absxx = np.absolute((group.loc[group['idx']==idx_post_bout,'propBoutAligned_x'].values - group.loc[group['idx']==idx_pre_bout,'propBoutAligned_x'].values))
    epochBouts_trajectory = np.degrees(np.arctan(yy/absxx)) # direction of the bout, -90:90
    pitch_pre_bout = group.loc[group.idx==idx_pre_bout,'propBoutAligned_pitch'].values
    pitch_initial = group.loc[group.idx==idx_initial,'propBoutAligned_pitch'].values

    pitch_peak = group.loc[group.idx==round_half_up(peak_idx),'propBoutAligned_pitch'].values
    pitch_mid_accel = group.loc[group.idx==round_half_up(idx_mid_accel),'propBoutAligned_pitch'].values
    pitch_post_bout = group.loc[group.idx==idx_post_bout,'propBoutAligned_pitch'].values
    traj_peak = group.loc[group['idx']==peak_idx,'propBoutAligned_instHeading'].values
    rot_l_decel = pitch_post_bout - pitch_peak
    rot_l_accel = pitch_peak - pitch_pre_bout
    rot_early_accel = pitch_mid_accel - pitch_pre_bout
    
    # group = group.reset_index(drop=True)
    # index_of_peak = group.loc[group.idx==round_half_up(peak_idx),:].index
    # smoothed_traj = savgol_filter(group['propBoutAligned_instHeading'],5,3)
    # smoothed_pitch = savgol_filter(group['propBoutAligned_pitch'],5,3)
    # traj_peak_smoothed = smoothed_traj[index_of_peak]
    # pitch_peak_smoothed = smoothed_pitch[index_of_peak]
    
    bout_features = pd.DataFrame(data={'pitch_pre_bout':pitch_pre_bout,
                                       'rot_l_accel':rot_l_accel,
                                       'rot_l_decel':rot_l_decel,
                                       'rot_pre_bout':pitch_pre_bout - pitch_initial,
                                       'rot_early_accel':rot_early_accel,
                                       'pitch_initial':pitch_initial,
                                       'bout_traj':epochBouts_trajectory,
                                       'traj_peak':traj_peak, 
                                       'traj_deviation':epochBouts_trajectory-pitch_pre_bout,
                                       'atk_ang':traj_peak-pitch_peak,
                                    #    'atk_ang_smoothed': traj_peak_smoothed - pitch_peak_smoothed,
                                       'spd_peak': group.loc[group.idx==round_half_up(peak_idx),'propBoutAligned_speed'].values,
                                       })
    features_all = pd.concat([features_all,bout_features],ignore_index=True)


    grp = group.groupby(np.arange(len(group))//(idxRANGE[1]-idxRANGE[0]))
    this_dpf_res = group.assign(
                                pitch_pre_bout = np.repeat(pitch_pre_bout,(idxRANGE[1]-idxRANGE[0])),
                                pitch_post_bout = np.repeat(pitch_post_bout,(idxRANGE[1]-idxRANGE[0])),

                                pitch_initial = np.repeat(pitch_initial,(idxRANGE[1]-idxRANGE[0])),
                                bout_traj = np.repeat(epochBouts_trajectory,(idxRANGE[1]-idxRANGE[0])),
                                traj_peak = np.repeat(traj_peak,(idxRANGE[1]-idxRANGE[0])),
                                pitch_peak = np.repeat(pitch_peak,(idxRANGE[1]-idxRANGE[0])),
                                
                                # traj_peak_smoothed = np.repeat(traj_peak_smoothed,(idxRANGE[1]-idxRANGE[0])),
                                # pitch_peak_smoothed = np.repeat(pitch_peak_smoothed,(idxRANGE[1]-idxRANGE[0])),
                                
                                bout_number = grp.ngroup(),
                                )
    this_dpf_res = this_dpf_res.assign(
                                atk_ang = this_dpf_res['traj_peak']-this_dpf_res['pitch_peak'],
                                # atk_ang_smoothed = this_dpf_res['traj_peak_smoothed']-this_dpf_res['pitch_peak_smoothed'],
                                traj_deviation = this_dpf_res['bout_traj']-this_dpf_res['pitch_pre_bout'],
                                )
    
    null_initial_pitch = grp.apply(
        lambda group: group.loc[(group['idx']>(peak_idx-idx_dur275ms))&(group['idx']<(peak_idx-idx_dur250ms)), 
                                'propBoutAligned_pitch'].mean()
    )

    # null_initial_angvel = grp.apply(
    #     lambda group: group.loc[(group['idx']>(peak_idx-idx_dur275ms))&(group['idx']<(peak_idx-idx_dur250ms)), 
    #                             'propBoutAligned_angVel'].mean()
    # )
    this_dpf_res = this_dpf_res.assign(
        pitch_chg_fromInitial = this_dpf_res['propBoutAligned_pitch'].values - np.repeat(null_initial_pitch,(idxRANGE[1]-idxRANGE[0])).values,
        pitch_chg_toPeak = this_dpf_res['pitch_peak'] - this_dpf_res['propBoutAligned_pitch'],
        pitch_chg_toPeak_abs = np.absolute(this_dpf_res['pitch_peak'] - this_dpf_res['propBoutAligned_pitch']),
        pitch_chg_toPostBout = this_dpf_res['pitch_post_bout'] - this_dpf_res['propBoutAligned_pitch'],

        # relative_angvel_change = this_dpf_res['propBoutAligned_angVel'].values - np.repeat(null_initial_angvel,(idxRANGE[1]-idxRANGE[0])).values,
    )
    this_dpf_res = this_dpf_res.assign(
        pitch_chg_subtracted = this_dpf_res['pitch_chg_fromInitial'] - this_dpf_res['pitch_chg_toPeak']
    )
    
    # correlation calculation -----------------------

    # Make a dictionary for correlation to be calculated
    corr_dict = {
        # "angVel_corr_preBoutPitch":['pitch_pre_bout','propBoutAligned_angVel'],
        # "angVel_corr_pitchPeak":['pitch_peak','propBoutAligned_angVel'],
        # 'angVel_corr_atkAng':['atk_ang','propBoutAligned_angVel'],
        # 'angVel_corr_trajDeviation':['traj_deviation','propBoutAligned_angVel'],
        # 'pitch_corr_traj':['propBoutAligned_pitch','propBoutAligned_instHeading'],
        # 'rotFromInitial_corr_trajDeviation':['pitch_chg_fromInitial','traj_deviation'],
        # 'rotFromInitial_corr_atkAng':['pitch_chg_fromInitial','atk_ang'],
        # 'rotToPeak_corr_atkAng':['pitch_chg_toPeak','atk_ang'],
        'rotToPostBout_corr_pitchInitial':['pitch_chg_toPostBout','pitch_initial'],

        # 'rotToPeakABS_corr_atkAng':['pitch_chg_toPeak_abs','atk_ang'],
        # 'rotSubtracted_corr_atkAng':['pitch_chg_subtracted','atk_ang']
        # 'rotFromInitial_corr_atkAng_sm':['pitch_chg_fromInitial','atk_ang_smoothed'],
        # 'rotToPeak_corr_atkAng_sm':['pitch_chg_toPeak','atk_ang_smoothed'],
       # 'angvelFromInitial_corr_atkAng':['relative_angvel_change','atk_ang'],\
        # 'tsp_corr_atkAng':['tsp','atk_ang'],
    }
    
    cat_cols = ['cond1','cond0']
    grp_cols = cat_cols + ['time_ms']
    
    df_to_corr = this_dpf_res#.loc[this_dpf_res['time_ms']<0]
    
    for i, name in enumerate(corr_dict):
        [col1, col2] = corr_dict[name]
        corr_thisName = corr_calc(df_to_corr, grp_cols, col1, col2, name)
        if i == 0:
            corr_res = corr_thisName
        else:
            corr_res = corr_res.join(corr_thisName)
    corr_res = corr_res.reset_index()
    corr_res = corr_res.assign(
        exp_num = excluded_exp,
    )
    corr_all = pd.concat([corr_all, corr_res])
    
corr_all = corr_all.reset_index(drop=True)
# corr_bySpd = corr_bySpd.reset_index(drop=True)
corr_all = corr_all.assign(
    score = corr_all['rotFromInitial_corr_atkAng'] - corr_all['rotToPeak_corr_atkAng']
)
# %%
# plot two correlations
for corr_which in corr_dict.keys():
    g = sns.relplot(
        # col='cond1',
        x='time_ms',
        y=corr_which,
        col='cond0',
        data=corr_all,
        kind='line',
        # col='cond0',
        hue='cond1',
        ci='sd',
        aspect=1.2,
        height=3
        )
    # g.set(xlim=(-250,0))
    # g.set(ylim=(-0.2,0.5))
    plt.savefig(fig_dir+f"/{corr_which}.pdf",format='PDF')

# plot subtracted value
# %%

p = sns.relplot(
    # col='cond1',
    x='time_ms',
    y='score',
    data=corr_all,
    col='cond0',
    kind='line',
    # col='cond0',
    hue='cond1',
    ci='sd',
    aspect=1.2,
    height=3
    )
p.set(xlim=(-250,0))
# p.set(ylim=(-0,0.5))

plt.savefig(fig_dir+f"/score.pdf",format='PDF')

# # %%
# corr_all.loc[corr_all['time_ms']>-100].groupby(['exp_num','cond1','cond0']).apply(
#     lambda bout: bout.loc[bout['score'].idxmax(),'time_ms']
# )
# %%
corr_all = corr_all.assign(
    score_sm = savgol_filter(corr_all['score'],3,2)
)
max_score_time = corr_all.groupby(['exp_num','cond1','cond0']).apply(
    lambda bout: bout.loc[bout['score'].idxmax(),'time_ms']
    ).reset_index()

max_score_time.groupby(['cond1','cond0']).median()
# %%
