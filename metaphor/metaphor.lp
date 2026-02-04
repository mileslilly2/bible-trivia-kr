% Demo ASP template
property(whirlwind, power).
property(whirlwind, uncontrollable).
property(whirlwind, meteorological).
property(whirlwind, material).
allowed(power). allowed(uncontrollable).
blocked(meteorological). blocked(material).
transfer(P) :- property(whirlwind, P), allowed(P).
:- transfer(P), blocked(P).
#show transfer/1.
