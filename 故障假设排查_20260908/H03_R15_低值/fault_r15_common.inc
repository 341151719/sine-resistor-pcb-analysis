* Common official-model topology for one fixed R16 case.
* R16VAL is set by the including deck and is never changed during a run.
.include "/mnt/c/Users/Administrator/Documents/稳定性原因分析CODEX/实际遇到的问题/opa548_shutdown_branch_spice_20260904/models/OPA548.LIB"
.include "/mnt/c/Users/Administrator/Documents/稳定性原因分析CODEX/实际遇到的问题/opa548_shutdown_branch_spice_20260904/models/OPA1656.LIB"
.param TEMP=27 R5OHM=100 R15VAL=1k
.options method=gear reltol=2e-4 abstol=1e-11 vntol=1e-8 gmin=1e-12 rshunt=1e12 maxord=2

* J2/U4 fixed +/-10 V; J1/OPA548 fixed +/-5 V; ES is OFF (0.6 V above V-).
VJ2P U4PLUS 0 10
VJ2N U4MINUS 0 -10
VJ1P VPLUS 0 5
VJ1N VMINUS 0 -5
VES ES VMINUS 0.6

* U4B input: only a 1 mV / 2 us startup kick.
VINPUT SRC 0 PULSE(0 1m 10u 20n 20n 2u 1)
RIN SRC U4P 100
CIN U4P 0 2p

* Other OPA1656 channel remains as package/rail load.
VUA U4AP 0 0
R13 U4AN 0 1k
R14 U4AO U4AN 49.9k
XU4A U4AP U4AN U4PLUS U4MINUS U4AO OPA1656
RU4AL U4AO 0 100k

* Extracted U4B feedback-route parasitics; copper is connected in all cases.
ROR16 U4O OR16M 5.380m
LOR16 OR16M R16O 4.1652n
COR16A U4O 0 0.3471p
COR16B R16O 0 0.3471p
RNR16 U4N NR16M 5.780m
LNR16 NR16M R16N 4.4694n
CNR16A U4N 0 0.37245p
CNR16B R16N 0 0.37245p
RNR15 U4N NR15M 6.723m
LNR15 NR15M R15N 5.6334n
CNR15A U4N 0 0.46945p
CNR15B R15N 0 0.46945p
R16 R16O R16N {R16VAL}
R15 R15N 0 {R15VAL}
* All C39 footprints are DNP; 0.05 pF is the pad-only baseline.
CDNP14 R16O R16N 0.05p
CDNP37 R16O R16N 0.05p
CDNP38 R16O R16N 0.05p
CDNP39 R16O R16N 0.05p
CDNP40 R16O R16N 0.05p
CDNP41 R16O R16N 0.05p
XU4 U4P U4N U4PLUS U4MINUS U4O OPA1656

* TP8 is before populated R5 (100 ohm).
RTP8 U4O TP8 1m
RTP8P TP8 0 10Meg
R5 TP8 OPA_P {R5OHM}

* Official OPA548 in unit-gain follower, with real output load.
RUNIT OPA_OUT OPA_N 1m
RILIM ILIM VMINUS 57.6k
XU1 OPA_P OPA_N ILIM VMINUS VPLUS OPA_OUT ES OPA548
RLOAD OPA_OUT SNUB 4.7
CLOAD SNUB 0 47n
RLEAK SNUB 0 1G
