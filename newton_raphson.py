import numpy as np
import copy

# f(x,y) = 2x^5 + y^3 - 2x^2.y - 4y
def grad_1(k): 
    x, y = k
    return np.array([
        10*x**4 - 4*x*y, 
        3*y**2 - 2*x**2 - 4
    ])

def hessian_1(k):
    x, y = k
    return np.array([
        [40*x**3 - 4*y, -4*x],
        [-4*x, 6*y]
    ])

# g(x, y) = x^4 + y^2 + 2xy + 1
def grad_2(u):
    x, y = u
    return np.array([
        4*x**3 + 2*y,
        2*y +2*x
    ])

def hessian_2(u):
    x, y = u
    return np.array([
        [12*x**2, 2],
        [2, 2]
    ])

# Thuật toán Newton-Raphson tìm điểm cực đại của một hàm thực vector sử dụng NumPy
def newton_optimizer(grad_fn, hessian_fn, u_0, tol=1e-8, max_iter=100):
    history = [u_0]
    u = copy.deepcopy(u_0)
    for _ in range(max_iter):
        grad = grad_fn(u)

        if np.linalg.norm(grad) <= tol:
            break 

        hessian = hessian_fn(u)
        #hessian_inv = np.linalg.inv(hessian)
        #u = grad @ hessian_inv
        #u = u + gra/hessian
        a = np.linalg.solve(hessian, grad)
        u = u - a
        history.append(copy.deepcopy(u))

    return history, u

u_0 = (15,15)
history, u = newton_optimizer(grad_1, hessian_1, u_0, max_iter=1_000)
print(u)
for i in range(len(history)):
    print(history[i])