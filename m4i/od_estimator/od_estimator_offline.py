# -*- coding: utf-8 -*-
"""
Created on Fri Jun 11 16:16:31 2021

@author: andge
"""
import copy
import dateutil
import numpy as np
import pandas as pd
from ..iniclass import IniClass
from ..matrix import MatrixODT, MatrixOD, MatrixAss
from ..connectors import Loader, Writer
from .od_estimator import ODEstimator

class ODEstimatorOffline(ODEstimator):


    def __init__(self, loader:Loader=None, writer: Writer = None, **kwargs):
        super().__init__(loader=loader, writer=writer, **kwargs)
        # Pesi F.O.
        self.gamma1 = self.ini.OD_ESTIMATION_GAMMA1
        self.gamma2 = self.ini.OD_ESTIMATION_GAMMA2
        self.gamma3 = self.ini.OD_ESTIMATION_GAMMA3
        # Parametri della ricerca del passo con metodo della sezione aurea
        self.itesa = self.ini.OD_ESTIMATION_ITESA
        self.lambdam = self.ini.OD_ESTIMATION_LAMBDA_LB # Estremo inferiore della ricerca monodimensionale
        self.lambdaM = self.ini.OD_ESTIMATION_LAMBDA_UB # Estremo superiore
        self.epsilon = self.ini.OD_ESTIMATION_EPS # Soglia di arresto dell'ottimizzazione monodimensionale
        self.epsilon2 = self.ini.OD_ESTIMATION_EPS2
        self.sa = self.ini.OD_ESTIMATION_SA # segmento minore della sezione aurea
        self.sb = 1-self.ini.OD_ESTIMATION_SA # segmento maggiore della sezione aurea
        self.gce=[]
        for i,t in enumerate(sorted(self.ODseed.keys())):
            self.gce.append(self.ODseed[t].mat)
        self.ite = 0
        self.fob = 1e308
        self.flows = None
        self.tstart = 0
        self.tend = 0
        self.OD = None
        self.M = None
        self.task_set_steps(steps=7+self.itesa)

    def update(self, OD:MatrixODT, M: MatrixAss, tstart:int, tend:int) -> MatrixODT:
        
        if self.ite==self.loader.ini.OD_ESTIMATION_MAX_ITE:
            self.ite=0
        self.ite+= 1
        self.OD: MatrixODT=OD
        self.M: MatrixAss=M
        self.tstart=tstart
        self.tend=tend
        self.tstart1:int=max(0,self.tstart-int(self.ini.OD_ESTIMATION_WHISKERS))
        self.tend1:int=min(1440,int(self.tend+self.ini.OD_ESTIMATION_WHISKERS))
        self.pre_int:int=int(self.loader.ini.OD_ESTIMATION_WHISKERS/self.ini.DELTA_T)
        self.t_intervals=list(range(self.tstart1,self.tend1,self.ini.DELTA_T))
        self.t_corr:list=list(range(tstart,int(tend),self.ini.DELTA_T))
        self.t_post:list=list(range(tstart,self.tend1,self.ini.DELTA_T))
        self.zone:list=self.loader.origins
        
        gi=[]
        gce=[]
        for i_item, item in enumerate(self.t_intervals):
            gi.append(np.ravel(self.OD[item].mat))
            gce.append(np.ravel(self.gce[int(i_item/self.ini.DELTA_T)]))
        
        #pdb.set_trace()
        pic = np.ones([len(self.loader.detectors), 1])
        qce = np.ones([len(gi[0]), 1])  
        #### CALCOLO FLUSSI
        flows=[]
        r2_i=[]
        r2_f=[]
        self.task_step_done(message=f"Initialization")
        for interval in self.t_post:
            flows_dep=np.zeros((1,self.M[0,0].mat.shape[0]))
            for dep in range(max(0,self.t_intervals.index(interval)-self.pre_int),self.t_intervals.index(interval)+1):
                flows_dep+=self.M[self.t_intervals.index(interval),dep].mat*gi[dep]
            tmp = self.counts.loc[self.counts['timestamp']==interval, ["id","counts"]]
            if self.ite==1:
                check_flows_i=tmp.copy().reset_index(drop=True)
                check_flows_i['flows']=flows_dep.transpose()
                #check_flows_i.to_excel('check_flows_i_'+str(interval)+'.xlsx')
                # import sklearn.metrics
                # r2_int_i=sklearn.metrics.r2_score(check_flows_i['counts'], check_flows_i['flows'])    
                # r2_i.append(r2_int_i)
            if self.ite==int(self.loader.ini.OD_ESTIMATION_MAX_ITE):
                check_flows_f=tmp.copy().reset_index(drop=True)
                check_flows_f['flows']=flows_dep.transpose()
                check_flows_f.to_excel('check_flows_f_'+str(interval)+'.xlsx')
                # import sklearn.metrics
                # r2_int_f=sklearn.metrics.r2_score(check_flows_f['counts'], check_flows_f['flows'])    
                # r2_f.append(r2_int_f)
                
            #pd.DataFrame(flows_dep).to_csv('flows_'+str(interval)+'_'+str(self.ite)+'.csv')
            flows.append(flows_dep)
        self.task_step_done(message=f"Preprocessing flows")
        # if self.ite==1:
        #         df_r2=pd.DataFrame()
        #         df_r2['interval']=self.t_post
        #         df_r2['r2']=r2_i 
        #         df_r2.to_excel('r2_i.xlsx')
        # if self.ite==int(self.loader.ini.STIMA_OD_MAX_ITE):
        #         df_r2=pd.DataFrame()
        #         df_r2['interval']=self.t_post
        #         df_r2['r2']=r2_i 
        #         df_r2.to_excel('r2_f.xlsx')
        
        
        
        #### CALCOLO FUNZIONE OBIETTIVO
        fob1=0
        fob2=0
       
        #### Calcolo FOB1 - Componente seed
       
        if self.gamma1!=0:
            for interval in self.t_corr:
                fob1+=(self.gamma1*(qce.transpose()*((gi[self.t_intervals.index(interval)]-gce[self.t_intervals.index(interval)])**2)).sum())
           
        #### Calcolo FOB2 - Componente conteggi 
        # TO DO: da modificare file conteggi!!!!!!!!!!!!!
       
        if self.gamma2!=0:
            for interval in self.t_post:
                fob2+=(self.gamma2*(pic.transpose()*((flows[self.t_post.index(interval)]-self.counts[self.counts['timestamp']==interval]['counts'].values)**2)).sum())
           
        self.fob=fob1+fob2
        self.task_step_done(message=f"Objective function calculation: FOB={self.fob}")
        
        
        
        
        ### CALCOLO DEL GRADIENTE
        self.grad=[]
        grad1=[]
        grad2=[]
        
        for interval in self.t_corr:
            grad1=self.gamma1*(qce.transpose()*(gi[self.t_intervals.index(interval)]-gce[self.t_intervals.index(interval)]))
            grad2_dep=np.zeros((1,len(gi[0])))
            for dep in range(max(0,self.t_intervals.index(interval)-self.pre_int),self.t_intervals.index(interval)+1):
                grad2_dep+=(self.M[self.t_intervals.index(interval),dep].mat.transpose()*(pic.transpose()*((flows[self.t_post.index(interval)]-self.counts[self.counts['timestamp']==interval]['counts'].values))).transpose()).transpose()
            grad2=grad2_dep
            self.grad.append(grad1+grad2)
            
        self.task_step_done(message=f"Gradient calculated")
        ### OTTIMIZZAZIONE: METODO SEZIONE AUREA
        
        ak = self.lambdam  # inizializzazione estremo inferiore
        bk = self.lambdaM  # inizializzazione estremo superiore
        
        gai = gi.copy()
        gbi = gi.copy()
        for interval in self.t_corr:
            gai[self.t_intervals.index(interval)]=gi[self.t_intervals.index(interval)]*(1-(ak*(self.grad[self.t_intervals.index(interval)-self.pre_int][0])))
            gbi[self.t_intervals.index(interval)]=gi[self.t_intervals.index(interval)]*(1-(bk*(self.grad[self.t_intervals.index(interval)-self.pre_int][0])))
            
        aak = ak + self.sa * (bk - ak)  # inizializzazione del valore intermedio minore
        bbk = ak + self.sb * (bk - ak)
        
        self.task_step_done(message=f"Starting golden section search with ak={ak}, aak={aak}, bk={bk}, bbk={bbk}")
        # Ricerca del passo ottimo
        
        for j in range(0, self.itesa):
            for interval in self.t_corr:
                gai[self.t_intervals.index(interval)]=gi[self.t_intervals.index(interval)]*(1-(aak*(self.grad[self.t_intervals.index(interval)-self.pre_int][0])))
                gbi[self.t_intervals.index(interval)]=gi[self.t_intervals.index(interval)]*(1-(bbk*(self.grad[self.t_intervals.index(interval)-self.pre_int][0])))
   
            ###CALCOLO FLUSSI PER GA e GI
        
            fla=[]
            flb=[]
            for interval in self.t_post:
                fla_dep=np.zeros((1,self.M[0,0].mat.shape[0]))
                flb_dep=np.zeros((1,self.M[0,0].mat.shape[0]))
                for dep in range(max(0,self.t_intervals.index(interval)-self.pre_int),self.t_intervals.index(interval)+1):
                    fla_dep+=self.M[self.t_intervals.index(interval),dep].mat*gai[dep]
                    flb_dep+=self.M[self.t_intervals.index(interval),dep].mat*gbi[dep]
                fla.append(fla_dep)
                flb.append(flb_dep)
        
        
            #### CALCOLO FUNZIONE OBIETTIVO
            fa1=0
            fa2=0
            fb1=0
            fb2=0
           
            #### Calcolo FA1 e FB1 - Componente seed
           
            for interval in self.t_corr:
                fa1+=(self.gamma1*(qce.transpose()*((gai[self.t_intervals.index(interval)]-gce[self.t_intervals.index(interval)])**2)).sum())
                fb1+=(self.gamma1*(qce.transpose()*((gbi[self.t_intervals.index(interval)]-gce[self.t_intervals.index(interval)])**2)).sum())
            #### Calcolo FOB2 - Componente conteggi 
            # TO DO: da modificare file conteggi!!!!!!!!!!!!!
           
            for interval in self.t_post:
                fa2+=(self.gamma2*(pic.transpose()*((fla[self.t_post.index(interval)]-self.counts[self.counts['timestamp']==interval]['counts'].values)**2)).sum())
                fb2+=(self.gamma2*(pic.transpose()*((flb[self.t_post.index(interval)]-self.counts[self.counts['timestamp']==interval]['counts'].values)**2)).sum())
            fa=fa1+fa2
            fb=fb1+fb2
            
            if fa > fb:
                ak = aak  # Nuovo estremo inferiore, posto uguale al valore intermedio minore
                aak = bbk  # Nuovo valore intermedio minore, posto uguale al valore intermedio maggiore
                bbk = ak + self.sb * (bk - ak)
            else:
                bk = bbk  # Nuovo estremo superiore, posto uguale al valore intermedio superiore
                bbk = aak  # Nuovo valore intermedio maggiore, posto uguale al valore intermedio minore
                aak = ak + self.sa * (bk - ak)  # Nuovo valore intermedio minore, calcolato sul nuovo segmento di estremi [ak, bk]

            self.task_step_done(message=f"Iteration {j+1}/{self.itesa}: ak={ak}, aak={aak}, bk={bk}, bbk={bbk}, fa={fa}, fb={fb}")
            if (bk - ak) < self.epsilon:                
                self.task_step_done(message=f"Convergence reached at iteration {j+1}/{self.itesa}. Remaining iterations skipped.", w=self.itesa-j)
                #for i in range(j, self.itesa):
                #    pass
                break
        
        ### Calcolo del passo ottimo
        
        lambdaopt=(bk + ak) / 2 
        yi=gi.copy()
        for interval in self.t_corr:
            yi[self.t_intervals.index(interval)]=gi[self.t_intervals.index(interval)]*(1-(lambdaopt*(self.grad[self.t_intervals.index(interval)-self.pre_int][0])))
            
        gi_old=gi.copy()
        alfa=1/(self.ite+1)
        od_new=gi_old.copy()
        
        for interval in self.t_corr:
            od_new[self.t_intervals.index(interval)]=gi_old[self.t_intervals.index(interval)]+alfa*(yi[self.t_intervals.index(interval)]-gi_old[self.t_intervals.index(interval)])
            od_new[self.t_intervals.index(interval)][od_new[self.t_intervals.index(interval)]<0]=1

        self.task_step_done(message=f"Optimal step calculated: lambdaopt={lambdaopt}, alfa={alfa}")
        gi=od_new.copy()
        OD_new=self.OD.copy()
        
        template = list(self.ODseed.values())[0].mat
        for interval in self.t_corr:
            ind_zone=0
            new_m=np.reshape(gi[self.t_intervals.index(interval)],[len(template),len(template)])
            tmp = OD_new[interval]
            for z in self.zone: 
                for j in self.zone:
                    pos=self.zone.index(j)
                    tmp[z,j]=new_m[ind_zone][pos]
                ind_zone+=1
        self.task_step_done(message=f"OD matrix updated for intervals {self.t_corr[0]} to {self.t_corr[-1]}")
            
        return OD_new  
            
    
    
#     a=4
#     indices=[(a,0),(a,1),(a,2),(a,3),(a,4),(a,5),(a,6),(a,7),(a,8),(a,9),(a,10),(a,11),(a,12),(a,13),(a,14),(a,15),(a,16),(a,17),(a,18),(a,19)]
#     for ind in indices:
#         pd.DataFrame(M.mats[ind].mat.toarray()).to_excel('M_'+str(ind)+'.xlsx')
        
        
# for i in range(0,91):
#     for j in range(0,i+1):
#         ind=(i,j)
#         a=pd.DataFrame(M.mats[ind].mat.toarray()).to_excel('M_'+str(ind)+'.xlsx')