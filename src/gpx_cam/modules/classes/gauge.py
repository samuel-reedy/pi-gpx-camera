class Gauge:
    sensitivity = 20
    ideal_depth = -1
        
    def set_parameters(self, sensitivity=None, ideal_depth=None):
        if sensitivity is not None:
            self.sensitivity = sensitivity
        if ideal_depth is not None:
            self.ideal_depth = ideal_depth

    def get_parameters(self):
        return {
            'sensitivity': self.sensitivity,
            'ideal_depth': self.ideal_depth
        }