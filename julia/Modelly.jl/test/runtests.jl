using Modelly
using PythonCall
using Test

target = Modelly.tutorial() * ":Epidemic"

@testset "Modelly.jl" begin
    @testset "parameters and a run" begin
        @test parameters(target).name == ["beta", "gamma", "population", "initial"]
        run = simulate(target; seed = 99, steps = 40, beta = 0.4)
        @test size(run, 1) == 41
        @test all(run.susceptible .+ run.infected .+ run.recovered .== 1000)
        @test run == simulate(target; seed = 99, steps = 40, beta = 0.4)
    end

    @testset "columns without a copy" begin
        m = model("modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"; seed = 1)
        wealth = column(m, "MoneyAgent", "wealth")
        @test sum(wealth) == length(wealth)
        wealth[1] = 99
        @test pyconvert(Int, Modelly.bindings.column(m, "MoneyAgent", "wealth")[0]) == 99
    end

    @testset "the SIR calibration tutorial" begin
        cases = simulate(target; seed = 99, steps = 40, beta = 0.4, gamma = 0.1).infected[2:end]
        fit = calibrate(target; priors = (beta = prior_uniform(0.05, 1.0),
                                          gamma = prior_uniform(0.02, 0.5)),
                        observed = (infected = cases,), steps = 40, particles = 100,
                        generations = 6, seed = 2027)
        s = fit.summary
        beta = s[s.parameter .== "beta", :]
        gamma = s[s.parameter .== "gamma", :]
        @test round(beta.mean[1]; digits = 3) == 0.423
        @test round(gamma.mean[1]; digits = 3) == 0.098
        @test beta.hdi_low[1] < 0.4 < beta.hdi_high[1]
        @test size(fit.particles, 1) == 100
    end
end
