from adversarial_trainer import * 
from categorical_kl_divergence import *
import numpy

class VirtualAdversarialTrainer(AdversarialTrainer):

    def __init__(self,nn,out_act_type='Softmax',epsilon=1.0,norm_constraint_type='L2',lamb=1.0,num_power_iteration=1,xi=1e-6):
        super(VirtualAdversarialTrainer,self).__init__(nn=nn,
                                    out_act_type=out_act_type,
                                    epsilon=epsilon,
                                    norm_constraint_type=norm_constraint_type,
                                    lamb=lamb)
        self.num_power_iteration = num_power_iteration
        self.xi=xi


    def cost_fitness_with_y(self,x,t,test=False,update_batchstat_estimation=True):
        y = self.nn.y_given_x(x,test,update_batchstat_estimation)
        if(self.out_act_type == 'Softmax' ):
            return F.softmax_cross_entropy(y,t),y
        elif(self.out_act_type == 'Linear'):
            return F.mean_squared_error(y,t),y
        else:
            raise NotImplementedError()

    def cost_virtual_adversarial_training(self,x,t,test=False,unchain_clean_y=True):
        cost_fitness,y = self.cost_fitness_with_y(x,t,test=test)
        py = self.nn.py_given_y(y)
        xvadv,ptb = self.get_virtual_adversarial_examples_for_py(x,py,test=test)
        py_given_xvadv = self.nn.py_given_x(xvadv,test,False)
        cost_fitness_vadv = categorical_kl_divergence(py,py_given_xvadv,unchain_py=unchain_clean_y)
        return cost_fitness, self.lamb*cost_fitness_vadv

    def get_virtual_adversarial_examples_for_py(self,x,py,test=False):
        xp = cupy.get_array_module(*x.data)
        d = xp.random.normal(size=x.data.shape,dtype='float32')
        for i in xrange(self.num_power_iteration):
            input_gradient_keeper = InputGradientKeeper()
            d = as_mat(d)
            x_xi_d = x + self.xi*normalize_axis1(d).reshape(x.data.shape)
            x_xi_d_ = input_gradient_keeper(x_xi_d)
            py_given_x_xi_d = self.nn.py_given_x(x_xi_d_,test,False)
            kl = categorical_kl_divergence(py,py_given_x_xi_d,unchain_py=True)
            kl.backward()
            d = input_gradient_keeper.gx
        if (self.norm_constraint_type == 'L2'):
            ptb = perturbation_with_L2_norm_constraint(d,self.epsilon)
        else:
            ptb = perturbation_with_max_norm_constraint(d,self.epsilon)
        xvadv = x + ptb.reshape(x.data.shape)
        return xvadv,ptb

    def get_virtual_adversarial_examples(self,x,test=False):
        py = self.nn.py_given_x(x,test,False)
        return self.get_virtual_adversarial_examples_for_py(x,py,test=test)



