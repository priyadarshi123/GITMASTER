class Car:

    def __init__(self,brand,maxspeed):
        self.brand= brand
        self.maxspeed=maxspeed


    def masterintro(self):
        print(f"my car brand is: {self.brand}")

    def speedintro(self):
        print(f"my car max speed is: {self.maxspeed}")


class Automobile(Car):
    def __init__(self,autopilot,brand,maxspeed):
        self.autopilot = autopilot
        super().__init__(brand,maxspeed)

    def autopilotintro(self):
        print(f'Autopilot is: {self.autopilot} , maxspeed is : {self.maxspeed}')

    def speedintro(self):
        print(f"mys cars maxs speeds is: {self.maxspeed}")










