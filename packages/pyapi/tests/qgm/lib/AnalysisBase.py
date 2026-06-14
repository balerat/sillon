# -*- coding: utf-8 -*-

from lib.shot import Shot
from lib.miscfitfunc import *
from lib.unitsReplacement import A, K, V, W
from .logsetup import log
from scipy import interpolate
import numpy as np
import matplotlib.pyplot as plt
import os
from scipy.optimize import curve_fit
import matplotlib
from PIL import Image
import math
import h5py
from tqdm import tqdm

cm = 1/2.54  # centimeters in inches

unitExponents={}
unitExponents['']=0
unitExponents['milli']=-3
unitExponents['micro']=-6
unitExponents['pico']=-9

unitPrefixes={}
unitPrefixes['']=''
unitPrefixes['milli']='$m$'
unitPrefixes['micro']='$\mu$'
unitPrefixes['pico']='$p$'


#==========================
#LOADING DATA
#==========================
def resetHDF5(oldFolder,newFolder):
    files = [f for f in os.listdir(oldFolder+'\\') if os.path.isfile(os.path.join(oldFolder+'\\', f))]
    files = [f for f in files if (f.endswith('.hdf5') and not f.endswith('analysis.hdf5'))]

    for f in files:
        print(f)
        with h5py.File(f'{newFolder}/{f}','w') as f_dest:
            with h5py.File(f'{oldFolder}/{f}','r') as f_src:
                f_src.copy(f_src['files'],f_dest,'files')
                f_src.copy(f_src['main'],f_dest,'main')
                f_src.copy(f_src['parameters'],f_dest,'parameters')
                f_src.copy(f_src['system.soft.YAxisCam'],f_dest,'system.soft.YAxisCam')
                
def loadData(folders,variables,rois,NRow=0,NCol=0,analysisframetype='OD',vmin=0,vmax=2,my_dir_save=None,plotImgs=True,verboseLog=False,titleVals=None,titleValUnits=None, verbose=False):
    if my_dir_save is None:
        my_dir_save='{}/Results'.format(folders[0])
    files=[]
    errorArr = []
    filenums=np.zeros(len(folders))
    for i in range(len(folders)):
        F=folders[i]
        filestemp = [f for f in os.listdir(F) if os.path.isfile(os.path.join(F, f))]
        filestemp = [f for f in filestemp if (f.endswith('.hdf5') and not f.endswith('analysis.hdf5'))]
        filestemp = sorted(filestemp)
        filenums[i]=len(filestemp)
        files=files+filestemp
    
    if NRow*NCol==0:
        NRow=1
        NCol=len(files)
    else:
        files = files[:NRow*NCol]
    
    roi=rois['main']

    r=[]
    i0=0

    printNum = len(files)//100
    printNum+=(printNum==0)
    
    if plotImgs:
        fig = plt.figure(1, figsize=(NCol*1.5,NRow*1.5),dpi=50)

    ImgArr = np.zeros((len(files),roi[1]-roi[0],roi[3]-roi[2]))
    ExtraImgArrs = {}
    for key in rois.keys():
        if (key!='bg' and key!='main'):
            temproi = rois[key]
            ExtraImgArrs[key] = np.zeros((len(files),temproi[1]-temproi[0],temproi[3]-temproi[2]))
    
    print('Loading Hdfs5 data')

    for i in tqdm(range(len(files))):
        try:
            tempdict={}

            if verboseLog:
                log.info(files[i])

            folderindex=0
            foldernum=0
            for j in range(len(folders)):
                foldernum+=filenums[j]
                if i0>=foldernum:
                    folderindex=j+1

            my_dir = folders[folderindex]
            if verboseLog:
                print('my_dir={}'.format(my_dir))
            run=Shot(my_dir,files[i])
            for v in variables:
                if v=='timestamp':
                    tempdict[v]=run.timestamp
                else:
                    tempdict[v]=run.userdata[v]
            


            a=run.get_frame(analysisframetype)
            a.roi=roi
            img=a.image_cropped
            # img=img-bg # Important change
            img[np.logical_or(np.isinf(img),np.isnan(img))]=img[np.logical_not(np.logical_or(np.isinf(img),np.isnan(img)))].max()
            img = np.flipud(img)
            ImgArr[i0,:,:] = img

            r.append(tempdict)

            if plotImgs:
                try:
                    img_bin = img.reshape(img.shape[0] // 2, 2, img.shape[1] // 2, 2).mean(3).mean(1)
                except:
                    img_bin=img
                ax = plt.subplot(NRow,NCol, i0+1)
                plt.imshow(img_bin, interpolation='None', cmap='Reds', vmin=vmin, vmax= vmax )  # jet

                if titleVals is not None:
                    titleStr=''               
                    for i in range(len(titleVals)):
                        try:
                            titleStr = titleStr + '{:.1f}{}'.format(run.userdata[titleVals[i]],titleValUnits[i])
                        except:
                            titleStr = titleStr + '{}{}'.format(run.userdata[titleVals[i]],titleValUnits[i])
                        if i<len(titleVals)-1:
                            titleStr = titleStr + ', '
                    
                    ax.set_title(titleStr)

                ax.set_xticks([])
                ax.set_yticks([])

            for key in rois.keys():
                if (key!='bg' and key!='main'):
                    a=run.get_frame(analysisframetype)
                    a.roi = rois[key]
                    img=a.image_cropped
                    img[np.logical_or(np.isinf(img),np.isnan(img))]=img[np.logical_not(np.logical_or(np.isinf(img),np.isnan(img)))].max()
                    img = np.flipud(img)
                    ExtraImgArrs[key][i0,:,:]=img
        except Exception as e:
            log.exception(e)
            errorArr.append(files[i])
            print('Error for {}'.format(i))
            r.append(np.nan)
            pass
        
        i0+=1
    
    for f in errorArr:
        print(f)
    
    if plotImgs:
        plt.tight_layout()
        plt.savefig(r'{}{}.png'.format(my_dir_save,'Imgs'), format = 'png',bbox_inches='tight', transparent=True,dpi=50)
        plt.clf()
        plt.close()

    # Convert list of dicts to dict of lists
    try:
        r = dict(zip(r[0],zip(*[d.values() for d in r])))
    except IndexError as e1:
        log.error('IndexError: {}. No files have been analysed.'.format(e1))
        r={}
    except Exception as e2:
        log.exception(e2)
        r={}

    for key in r.keys():
        r[key]=np.array(r[key])
    
    if len(rois.keys())>2:
        return ImgArr, ExtraImgArrs, r
    else:
        return ImgArr, r

#==========================
#PLOTTING
#==========================
def setupPlotParams():
    matplotlib.rc('font',size=7)
    matplotlib.rc('font',weight='normal')
    matplotlib.rc('font',family='Arial')
    matplotlib.rc('axes',titlesize=7)
    matplotlib.rc('axes',titleweight='normal')
    matplotlib.rc('axes',labelsize=7)
    matplotlib.rc('axes',labelweight='normal')
    matplotlib.rc('xtick',labelsize=7)
    matplotlib.rc('ytick',labelsize=7)
    matplotlib.rc('figure',dpi=300)
    matplotlib.rc('lines',linewidth=1)
    matplotlib.rc('lines',mew=1)
    matplotlib.rc('lines',markersize=4)
    matplotlib.rc('xtick.major',size=1)
    matplotlib.rc('ytick.major',size=1.5)
    matplotlib.rc('legend',title_fontsize=6)
    matplotlib.rc('xtick',bottom=True)
    matplotlib.rc('xtick',top=True)
    matplotlib.rc('xtick',direction='in')
    matplotlib.rc('ytick',left=True)
    matplotlib.rc('ytick',right=True)
    matplotlib.rc('ytick',direction='in')
    matplotlib.rc('legend',edgecolor='none')

def gifGen(folders,rois,t_var,savedir,vmin=0,vmax=4,plotAll=False,timeUnits='micro'):
    
    tConversionExp=-unitExponents[timeUnits]
    tUnitPrefix=unitPrefixes[timeUnits]

    imgs,r=loadData(folders,variables=[t_var],rois=rois)
    t=r[t_var]

    frames=[]
    fig=plt.figure(figsize=(3*cm,3*cm),facecolor=(1.0,1.0,1.0,0.0))
    ax=fig.add_subplot()
    ax.tick_params('both',bottom=False,left=False,right=False,top=False,labelleft=False,labelbottom=False)
    img = ax.imshow(np.flipud(imgs[0]),cmap='Reds',vmin=vmin,vmax=vmax)
    ax.set_title('{:.1f}$\mu s$'.format(t[0]))
    fig.tight_layout()
    def update(index):
        ax.set_title('{:.1f}{}$s$'.format(t[index]*10**tConversionExp,tUnitPrefix))
        img.set_data(np.flipud(imgs[index]))
    for i in range(len(imgs)):
        update(i)
        fig.canvas.draw()
        PIL_Img=Image.frombytes('RGBA',fig.canvas.get_width_height(),fig.canvas.buffer_rgba())
        frames.append(PIL_Img)

    frames[0].save('{}/Anim.gif'.format(savedir), format='GIF', append_images=frames[1:], save_all=True, duration=5, loop=0,disposal=2)

    plt.close()
    plt.clf()
    if plotAll:
        N=len(imgs)
        N_x=int(np.sqrt(N))
        N_y=math.ceil(N/N_x)
        fig=plt.figure(figsize=(8.9*cm,8.9*cm*N_y/N_x))
        for i in range(N):
            ax=fig.add_subplot(N_y,N_x,i+1)
            ax.imshow(np.flipud(imgs[i]),cmap='Reds',vmin=vmin,vmax=vmax)
            ax.set_title('{:.1f}{}$s$'.format(t[i]*10**tConversionExp,tUnitPrefix))
            ax.tick_params('both',labelbottom=False,labelleft=False)
        fig.tight_layout()
        plt.savefig('{}/Imgs.png'.format(savedir))

#==========================
#FITTING
#==========================

def gaussian(x,A,x0,s,c):
    return A*np.exp(-(x-x0)**2/(2*s**2))+c

def GaussFit1D(x,y):
    xrange = x.max()-x.min()
    p0=(y.max(),np.mean(x),xrange/8.,0)
    popt,pcov = curve_fit(gaussian,x,y,p0=p0)
    return popt,pcov

def gauss_2d(coords,A,x0,y0,sx,sy,c):
    x=coords[0]
    y=coords[1]
    return A*np.exp(-(x-x0)**2/(2*sx**2) - (y-y0)**2/(2*sy**2))+c

def GaussFit2D(X,Y,img,p0=None):
    if p0 is None:
        p0=(img.max()-img.min(),np.mean(X),np.mean(Y),np.std(X),np.std(Y),img.min())
    popt,pcov=curve_fit(gauss_2d,(X.ravel(),Y.ravel()),img.ravel(),p0=p0)
    return popt[3],popt[4],popt

def TF(coords,A,X0,Y0,rx,ry,c):
    x=coords[0]
    y=coords[1]
    return A*np.maximum(1-((x-X0)/rx)**2-((y-Y0)/ry)**2,np.zeros(x.shape))**1.5+c

def get_g2Func(N):
    z=np.arange(0,1.0001,0.0001)
    z=np.tile(z,(N,1))
    p=np.ones(z.shape)
    for i in range(N):
        p[i]=p[i]*(i+1)
    res = np.sum(z**p/p**2,axis=0)
    g2Func = interpolate.interp1d(np.arange(0,1.0001,0.0001),res,kind='linear')
    return g2Func

def modifiedGauss2D(coords, A,X0,Y0,sx,sy,c,g2Func):
    x=coords[0]
    y=coords[1]
    return A*g2Func(np.exp(-(x-X0)**2/(2*sx**2)-(y-Y0)**2/(2*sy**2)))

def bimodalBECFit(X,Y,img,g2func=get_g2Func(500),r_TFCutoff=1.2,showPlots=False):
    
    def BimodalFunctionRough(coords, A_th,X0,Y0,sx_th,sy_th, A_c,rx_c,ry_c, Offset):
        return modifiedGauss2D(coords, A_th,X0,Y0,sx_th,sy_th,0,g2func) + TF(coords,A_c,X0,Y0,rx_c,ry_c,0) + Offset

    def ThermFunction(coords, A_th,X0_th,Y0_th,sx_th,sy_th, Offset,mx,my):
        return modifiedGauss2D(coords, A_th,X0_th,Y0_th,sx_th,sy_th,0,g2func) + mx*coords[0]+my*coords[1]+Offset
    
    #First do a rough fit of the full function with no background gradients etc.
    p0_rough = (np.max(img)/2.,0.,0.,np.max(X)/4.,np.max(X)/4.,                 #Thermal part
                np.max(img)/2.,15.,15.,                                         #BEC part
                0.)                                                             #Offset
    
    ub_rough = (np.max(img)*2,np.max(X),np.max(Y),np.max(X)*2.,np.max(Y)*2.,    #Thermal part
                np.max(img)*2.,40.,40.,                                         #BEC part
                0.2)                                                            #Offset
    
    lb_rough = (0.,np.min(X),np.min(Y),1.,1.,                                   #Thermal part
                0.,1.,1.,                                                       #BEC part
                -0.2)                                                           #Offset

    try:
        popt_rough,pcov_rough = curve_fit(BimodalFunctionRough,(X.ravel(),Y.ravel()),img.ravel(),p0=p0_rough,bounds=(lb_rough,ub_rough))
    except:
        popt_rough = p0_rough
        fitFailed_r = 1
        
    X0_rough = popt_rough[1]
    Y0_rough = popt_rough[2]
    rx_c_rough = popt_rough[6]
    ry_c_rough = popt_rough[7]
    
    popt_rough_th = popt_rough[:5]
    popt_rough_c = popt_rough[np.array([5,1,2,6,7])]
    popt_rough_bg = popt_rough[8]

    #Now fit the Gaussian, including any background gradients this time, and excluding the central region around the condensate
    indices = np.where(np.sqrt((X-X0_rough)**2/rx_c_rough**2+(Y-Y0_rough)**2/ry_c_rough**2)>r_TFCutoff)
    
    p0_therm = (popt_rough_th[0],popt_rough_th[1],popt_rough_th[2],popt_rough_th[3],popt_rough_th[4],   #Thermal part
                0.,0.,0.)                                                                               #Offset
    
    ub_therm = (np.max(img)*2,np.max(X),np.max(Y),np.max(X)*2.,np.max(Y)*2.,                            #Thermal part
                0.2,0.001,0.001)                                                                        #Offset
    
    lb_therm = (0.,np.min(X),np.min(Y),1.,1.,                                                           #Thermal part
                -0.2,-0.001,-0.001)                                                                     #Offset

    try:
        popt_therm_fit,pcov_therm_fit = curve_fit(ThermFunction,(X[indices],Y[indices]),img[indices],p0=p0_therm,bounds=(lb_therm,ub_therm))
    except:
        popt_therm_fit = p0_therm
        fitFailed_th = 0

    popt_therm = popt_therm_fit[:5]
    popt_bg = popt_therm_fit[5:]
    
    A_th,X0_th,Y0_th,sx_th,sy_th = popt_therm
    Offset_th,mx_th,my_th = popt_bg

    def BimodalFunctionFull(coords, A_c,X0_c,Y0_c,rx_c,ry_c):
        return modifiedGauss2D(coords, A_th,X0_th,Y0_th,sx_th,sy_th,0,g2func) + TF(coords,A_c,X0_th+X0_c,Y0_th+Y0_c,rx_c,ry_c,0) + mx_th*coords[0]+my_th*coords[1]+Offset_th

    #Now fit the full function, with the thermal and background parts set by the previous fit
    p0_c = (popt_rough[5],0.,0.,popt_rough[6],popt_rough[7])    #BEC part
    
    lb_c = (np.max(img)*2.,sx_th,sy_th,40.,40.)                 #BEC part

    ub_c = (0.,-sx_th,-sy_th,1.,1.)                             #BEC part
    try:
        popt_c,pcov_c = curve_fit(BimodalFunctionFull,(X.ravel(),Y.ravel()),img.ravel(),p0=p0_c,bounds=(ub_c,lb_c))
    except:
        print('FIT FAILED')
        popt_c=(0,0,0,0,0)
        fitFailed_c = 1
        
    xfine = np.arange(np.min(X),np.max(X)+0.5,0.5)
    Lx = len(xfine)
    yfine = np.arange(np.min(Y),np.max(Y)+0.5,0.5)
    Ly = len(yfine)
    xfine,yfine = np.meshgrid(xfine,yfine)
    
    BECNum = np.sum(TF((xfine,yfine),*popt_c))
    ThermalNum = np.sum(modifiedGauss2D((xfine,yfine),*popt_therm,0,g2func))

    def bgFunction(coords):
        return mx_th*coords[0]+my_th*coords[1]+Offset_th
    def TFFunction(coords, A_c,X0_c,Y0_c,rx_c,ry_c):
        return TF(coords,A_c,X0_th+X0_c,Y0_th+Y0_c,rx_c,ry_c)
    
    #Plot the results
    if showPlots:
        fig=plt.figure(figsize=(20,10))
        ax1=fig.add_subplot(1,2,1)
        ax1.imshow(img,cmap='Reds',vmin=0,vmax=4,interpolation='None')
        ax1.set_title('Data')
        
        ax2=fig.add_subplot(1,2,2)
        ax2.imshow(BimodalFunctionFull((xfine,yfine),*popt_c),cmap='Reds',vmin=0,vmax=4,interpolation='None')
        ax2.set_title('Fit')

        plt.show()

        fig=plt.figure(figsize=(20,10))
        ax1=fig.add_subplot(1,2,1)
        ax1.plot(xfine[Ly//2],BimodalFunctionFull((xfine,yfine),*popt_c)[Ly//2],'k--')
        ax1.plot(xfine[Ly//2],modifiedGauss2D((xfine,yfine),*popt_therm,0,g2func)[Ly//2],'r--')
        ax1.plot(xfine[Ly//2],TFFunction((xfine,yfine),*popt_c)[Ly//2],'b--')
        ax1.plot(xfine[Ly//2],bgFunction((xfine,yfine))[Ly//2],'g--')
        
        ax1.plot(X[img.shape[0]//2],img[img.shape[0]//2],'ko',mfc='w')
        
        ax2=fig.add_subplot(1,2,2)
        ax2.plot(yfine[:,Lx//2],BimodalFunctionRough((xfine,yfine),*popt_rough)[:,Lx//2],'k--')
        ax2.plot(yfine[:,Lx//2],modifiedGauss2D((xfine,yfine),*popt_rough_th,0,g2func)[:,Lx//2],'r--')
        ax2.plot(yfine[:,Lx//2],TFFunction((xfine,yfine),*popt_rough_c)[:,Lx//2],'b--')
        ax2.plot(yfine[:,Lx//2],bgFunction((xfine,yfine))[:,Lx//2],'g--')
        ax2.plot(Y[:,img.shape[1]//2],img[:,img.shape[1]//2],'ko',mfc='w')

        plt.show()

    
    return popt_rough, BECNum, ThermalNum, fitFailed_r, fitFailed_th, fitFailed_c

def TFFit2D(X,Y,img):
    p0=(img.max(),0,0,10,10,0,0)
    popt,pcov=curve_fit(TF,(X.ravel(),Y.ravel()),img.ravel(),p0=p0)
    return popt[3],popt[4],popt

def fitWidths(ImgArr,fitMethod=GaussFit2D):
    dataShape=ImgArr.shape[:-2]
    N=np.prod(dataShape)
    Lx = ImgArr.shape[-1]
    Ly = ImgArr.shape[-2]
    ImgReshape=ImgArr.ravel()
    ImgReshape=ImgReshape.reshape(N,Ly,Lx)

    x=np.arange(0,Lx,1.)-Lx/2.-0.5
    y=np.arange(0,Ly,1.)-Ly/2.-0.5
    X,Y=np.meshgrid(x,y)

    wx=np.zeros(N)
    wy=np.zeros(N)

    print('Fitting widths')
    for i in range(N):
        print('{:.1f}%'.format(i*100./N))
        img=ImgReshape[i]
        wx[i],wy[i],popt=fitMethod(X,Y,img)
    wx=wx.reshape(dataShape)
    wy=wy.reshape(dataShape)
    return wx,wy