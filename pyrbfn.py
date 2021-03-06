import numpy as np


class RadialBasisFunctionNeurons(object):
    """
    Abstract class for defining radial basis function neurons that populate
    the hidden layer of a radial basis function network.
    """
    def __init__(self):
        # Intermediate values used during training
        self.c = None

    def get_distance(self, x):
        """
        Calculate the distance i.e. norm of the input vector x from the center
        vector of the neurons.
        """
        raise NotImplementedError

    def activation(self, x):
        """
        The activation of the basis functions for a given input.
        """
        raise NotImplementedError


class GaussianRBF(RadialBasisFunctionNeurons):
    def __init__(self, mu, sigma):
        super(GaussianRBF, self).__init__()
        self.mu = mu
        self.sigma = sigma

    def get_distance(self, x):
        return (x - self.mu) / self.sigma

    def activation(self, x):
        self.c = self.get_distance(x)
        return np.exp(-0.5*np.sum(self.c**2, axis=1))


class VonMisesRBF(RadialBasisFunctionNeurons):
    def __init__(self, mu, kappa):
        super(VonMisesRBF, self).__init__()
        self.mu = mu
        self.kappa = kappa

    def get_distance(self, x):
        return self.kappa * np.cos(x - self.mu)

    def activation(self, x):
        self.c = self.get_distance(x)
        return np.exp(np.sum(self.c, axis=1))


class RBFN(object):
    """
    Radial Basis Function Network
    """
    def __init__(self, neurons, indim, bases, outdim, alpha):
        # Network architecture
        self.neurons = neurons
        self.indim = indim
        self.bases = bases**indim
        self.outdim = outdim
        self.alpha = alpha

        self.weights = 2*np.random.random((outdim, self.bases)) - 1

        # Intermediate values used in training
        self.h = None

    def evaluate(self, x):
        """
        Evaluate the response of the network for a given input.
        """
        g = self.neurons.activation(x)
        self.h = np.ones((self.outdim, 1)) * g.reshape((1, len(g)))
        a = self.h * self.weights
        return np.sum(a, axis=1)

    def train(self, x, y):
        """
        Train the network to learn the map of x -> y using iterative gradient
        descent.

        x is assumed to be of shape (samples, indim)
        y is assumed to be of shape (samples, outdim)
        """
        for _x, _y in zip(x, y):
            p = self.evaluate(_x)
            error = _y - p
            delta = self.alpha * error.reshape((len(error), 1)) * self.h
            self.weights += delta

        return self


class NormalizedRBFN(RBFN):
    def evaluate(self, x):
        """
        Evaluate the response of the network for a given input.
        """
        g = self.neurons.activation(x)
        g /= np.sum(g)
        self.h = np.ones((self.outdim, 1)) * g.reshape((1, len(g)))
        a = self.h * self.weights
        return np.sum(a, axis=1)


class HyperplaneRBFN(NormalizedRBFN):
    def __init__(self, neurons, indim, bases, outdim, alpha):
        super(HyperplaneRBFN, self).__init__(neurons, indim, bases, outdim,
                                             alpha)
        self.center_weights = 2*np.random.random((outdim, self.bases, indim))-1

    def evaluate(self, x):
        g = self.neurons.activation(x)
        g /= np.sum(g)
        self.h = np.ones((self.outdim, 1)) * g.reshape((1, len(g)))
        w = self.center_weights * self.neurons.c
        a = self.h * (self.weights + np.sum(w, axis=2))
        return np.sum(a, axis=1)

    def train(self, x, y):
        for _x, _y in zip(x, y):
            p = self.evaluate(_x)
            error = _y - p

            delta = self.alpha * error.reshape((len(error), 1)) * self.h
            self.weights += delta

            c_delta = ((np.ones(self.center_weights.shape) *
                       delta.reshape((self.outdim, self.bases, 1))) *
                       self.neurons.c)
            self.center_weights += c_delta

        return self


class AdaptiveRBFN(NormalizedRBFN):
    def __init__(self, neurons, indim, bases, outdim, alpha, eta):
        """Assumes Gaussian neurons"""
        super(AdaptiveRBFN, self).__init__(neurons, indim, bases, outdim,
                                           alpha)
        self.eta = eta

    def train(self, x, y):
        for _x, _y in zip(x, y):
            p = self.evaluate(_x)
            error = _y - p

            delta = error.reshape((len(error), 1)) * self.h
            self.weights += self.alpha * delta

            m1 = 2*self.neurons.c / self.neurons.sigma  # (bases, indim)
            m2 = self.weights - p.reshape((len(p), 1))  # (outdim, bases)

            m1 = np.tile(m1, (self.outdim, 1, 1))  # (outdim, bases, indim)
            m2 = np.tile(np.expand_dims(m2, axis=2), (1, 1, self.indim))
            delta = np.tile(np.expand_dims(delta, axis=2), (1, 1, self.indim))

            m_delta = self.eta * np.sum(delta * (m1 * m2), axis=0)

            self.neurons.mu += m_delta
            self.neurons.sigma += m_delta * self.neurons.c

        return self


class AdaptiveHyperplaneRBFN(HyperplaneRBFN):
    def __init__(self, neurons, indim, bases, outdim, alpha, eta):
        """Assumes Gaussian neurons"""
        super(AdaptiveHyperplaneRBFN, self).__init__(neurons, indim, bases,
                                                     outdim, alpha)
        self.eta = eta

    def train(self, x, y):
        for _x, _y in zip(x, y):
            p = self.evaluate(_x)
            error = _y - p

            delta = error.reshape((len(error), 1)) * self.h
            self.weights += self.alpha * delta

            c_delta = ((np.ones(self.center_weights.shape) *
                       delta.reshape((self.outdim, self.bases, 1))) *
                       self.neurons.c)
            self.center_weights += c_delta

            m1 = 2*self.neurons.c / self.neurons.sigma
            m2 = np.sum(self.center_weights*self.neurons.c, axis=2)
            m3 = self.weights - p.reshape((len(p), 1))
            m4 = self.center_weights / self.neurons.sigma

            m1 = np.tile(m1, (self.outdim, 1, 1))
            m2 = np.tile(np.expand_dims(m2, axis=2), (1, 1, self.indim))
            m3 = np.tile(np.expand_dims(m3, axis=2), (1, 1, self.indim))
            delta = np.tile(np.expand_dims(delta, axis=2), (1, 1, self.indim))

            m_delta = self.eta * np.sum(delta * (m1 * (m2 + m3) - m4), axis=0)

            self.neurons.mu += m_delta
            self.neurons.sigma += m_delta * self.neurons.c

        return self