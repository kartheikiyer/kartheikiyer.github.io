import numpy as np
import george
from george import kernels
from scipy.optimize import minimize

import warnings
warnings.filterwarnings('ignore')

from astropy.cosmology import FlatLambdaCDM
cosmo = FlatLambdaCDM(H0=70, Om0=0.3)

def neg_ln_like(p, gp, y):
    gp.set_parameter_vector(p)
    return -gp.log_likelihood(y)

def grad_neg_ln_like(p, gp, y):
    gp.set_parameter_vector(p)
    return -gp.grad_log_likelihood(y)

def gp_sfh_george(sfh_tuple,zval=5.606,vb = False,std=False, sample_posterior = False, n_samples = 10):
    """
    Create a GP-approximation of an SFH based on the george GP package by DFM:
    mass = stellar mass
    sfr = current sfr, averaged over some timescale the SED is sensitive to, 10-100Myr
    Nparam = number of parameters. 1=t50, 2=t33,t67, 3=t25,t50,75 etc
    param_arr = the numpy array of actual parameters

    """

    mass = sfh_tuple[0]
    #sfr = 10**sfh_tuple[1]
    sfr = sfh_tuple[1]
    Nparam = int(sfh_tuple[2])
    param_arr = sfh_tuple[3:]

    # this is the times at which the galaxy formed x percentiles of its observed stellar mass...
    input_Nparams = Nparam
    input_params = param_arr

    # these are time quantities (tx)
    input_params_full = np.zeros((input_Nparams+5,))
    input_params_full[0] = 0
    input_params_full[1] = 0.01
    input_params_full[2:-3] = input_params
    input_params_full[-3] = 0.998
    input_params_full[-2] = 0.999
    input_params_full[-1] = 1

    # these are galaxy mass quantities M(t)
    temp_mass = np.linspace(0,1,input_Nparams+2)
    input_mass = np.zeros((input_params_full.shape))

    input_mass[1] = 0.0
    input_mass[2] = 1e-1
    input_mass[2:-3] = temp_mass[1:-1]
    input_mass[-3] = 1.0 - np.power(10,sfr)*(1.0-0.998)*(cosmo.age(zval).value*1e9)/np.power(10,mass)
    input_mass[-2] = 1.0 - np.power(10,sfr)*(1.0-0.999)*(cosmo.age(zval).value*1e9)/np.power(10,mass)
    input_mass[-1] = 1.0
    # the last two statements help to fix the SFR at t_obs

    xax = input_params_full
    yax = (input_mass)
    yerr = np.zeros_like(yax)
    #yerr[1:-3] = yax[1:-3]*0.05
    #yerr[2:-3] = (1-yax[2:-3])*0.05
    #yerr[2:-3] = 0.05
    yerr[2:-3] = 0.001/np.sqrt(Nparam)
#     if Nparam > 20:
#         yerr[2:-3] = 0.1/np.sqrt(Nparam)

    #------------------------------------

    #kernel = DotProduct(10.0, (1e-2,1e2)) *RationalQuadratic(0.1)
    #gp = GaussianProcessRegressor(kernel=kernel, n_restarts_optimizer=9)
    #gp.fit(xax,yax)

    #x = np.linspace(0,1,1000)
    #y_pred, sigma = gp.predict(x[:,np.newaxis], return_std=True)
    #y_pred = y_pred.ravel() + x

    #------------------------------------


    #kernel = np.var(yax) * kernels.ExpSquaredKernel(np.median(yax)+np.std(yax))
    #k2 = np.var(yax) * kernels.LinearKernel(np.median(yax),order=1)
    kernel = np.var(yax) * kernels.Matern32Kernel(np.median(yax)) #+ k2
    gp = george.GP(kernel)

    #print(xax.shape, yerr.shape)

    gp.compute(xax.ravel(), yerr.ravel())

    x_pred = np.linspace(np.amin(xax), np.amax(xax), 1000)
    pred, pred_var = gp.predict(yax.ravel(), x_pred, return_var=True)
    y_pred = pred

    if sample_posterior == True:

        #print('this is happening!')
        samples = np.zeros((len(x_pred),n_samples))


        time_unnormed = x_pred*cosmo.age(zval).value*1e9

        for i in tqdm(range(n_samples)):
            temp = gp.sample_conditional(yax,x_pred)

            mass_unnormed = temp*np.power(10,mass)
            sfr_unnormed = np.diff(mass_unnormed)/np.diff(time_unnormed)
            samples[1:,i] = sfr_unnormed

        samples[samples<0] = 0

        return samples


    #print("Initial ln-likelihood: {0:.2f}".format(gp.log_likelihood(yax.ravel())))

    result = minimize(neg_ln_like, gp.get_parameter_vector(), jac=grad_neg_ln_like, args=(gp,yax))
    #print(result)

    gp.set_parameter_vector(result.x)
    #print("\nFinal ln-likelihood: {0:.2f}".format(gp.log_likelihood(yax.ravel())))

    y_pred, pred_var = gp.predict(yax.ravel(), x_pred, return_var=True)


    #------------------------------------

    mass_unnormed = y_pred*np.power(10,mass)
    time_unnormed = x_pred*cosmo.age(zval).value*1e9
    #print(np.amax(time_unnormed))

    sfr_unnormed = np.diff(mass_unnormed)/np.diff(time_unnormed)
    gen_sfh = np.zeros((mass_unnormed.shape))
    gen_sfh[1:] = sfr_unnormed

    mask = (gen_sfh<0)
    gen_sfh[mask] = 0



    #y_mean, y_cov = gp.predict(X_[:,np.newaxis], return_cov=True)
    if vb == True:
        plt.figure(figsize=(15,15))
        #plt.plot(input_params_full,input_mass,'k.',markersize=15)
        plt.errorbar(xax,yax,yerr=yerr, markersize=15, marker='o',lw=0,elinewidth=2)
        plt.plot(x_pred,y_pred,'g--')
        plt.fill_between(x_pred,y_pred.ravel()- np.sqrt(pred_var),y_pred.ravel() + np.sqrt(pred_var),alpha=0.1,color='g')
        #plt.axis([0,1,0,1])
        plt.xlabel('normalized time')
        plt.ylabel('normalized mass')
        plt.show()

        plt.plot(np.amax(time_unnormed)/1e9-time_unnormed/1e9,gen_sfh,'k-',lw=3)
        plt.xlabel('t [lookback time; Gyr]',fontsize=14)
        plt.ylabel('SFR(t) [solar masses/yr]',fontsize=14)
        plt.show()

    if std == False:
        return gen_sfh, time_unnormed
    else:
        mass_sigmaup_unnormed = (y_pred.ravel() + np.sqrt(pred_var))*np.power(10,mass)
        mass_sigmadn_unnormed = (y_pred.ravel() - np.sqrt(pred_var))*np.power(10,mass)
        sfr_sigmaup_unnormed = np.diff(mass_sigmaup_unnormed)/np.diff(time_unnormed)
        sfr_sigmadn_unnormed = np.diff(mass_sigmadn_unnormed)/np.diff(time_unnormed)
        gen_sfh_up = np.zeros((mass_unnormed.shape))
        gen_sfh_dn = np.zeros((mass_unnormed.shape))
        gen_sfh_up[1:] = sfr_sigmaup_unnormed
        gen_sfh_dn[1:] = sfr_sigmadn_unnormed

        maskup = (gen_sfh_up < 0)
        maskdn = (gen_sfh_dn < 0)

        gen_sfh_up[maskup] = 0
        gen_sfh_dn[maskdn] = 0
        return gen_sfh, gen_sfh_up, gen_sfh_dn, time_unnormed

    
def calctimes(timeax,sfh,nparams):
    
    massint = np.cumsum(sfh)
    massint_normed = massint/np.amax(massint)
    tx = np.zeros((nparams,))
    for i in range(nparams):
        tx[i] = timeax[np.argmin(np.abs(massint_normed - 1*(i+1)/(nparams+1)))]
        #tx[i] = (np.argmin(np.abs(massint_normed - 1*(i+1)/(nparams+1))))
        #print(1*(i+1)/(nparams+1))
        
    #mass = np.log10(np.sum(sfh)*1e9)
    mass = np.log10(np.trapz(sfh,timeax*1e9))
    sfr = np.log10(sfh[-1])
        
    return mass, sfr, tx