#!/usr/bin/python3
"""
NAMD-xtb interface v0.1 beta

by Haohao Fu
fhh2626_at_gmail.com
"""

"""
Readme:
    this script enables NAMD-xtb QM/MM simulation and non-periodic
    semi-emperial BOMD.
    Electrostatic embedding was implemented. GFN-xtb hamiltonian
    is used by default. If one wants to use other QM method, one can
    change the source code accordingly.
    
Requirement:
    Python 3 and numpy (I think Python 2.7+ is also possible)

Usage:
    In NAMD config file:
        qmSoftware     "custom"
        qmExecPath     xxxxx/namd_xtb.py
        
        QMElecEmbed, qmConfigLine, qmMult, qmCharge are useless.
    
    Then set XTBDIR and QMCHARGE below.
"""

# the complete directory of xtb program
XTBDIR = r'/home/chinfo/software/chem/xtb/xtb'
# the charge of each independent QM part
QMCHARGE = [0]

import os
import subprocess
import sys
import numpy as np

def read_namdinput(file):
    ''' read namd qmmm input file (file)
        return:
        qm atom -- element (python array)
        atomic coordinates -- coor (n * 3D numpy array)
        point charge + coor -- pcharge (n * 4D numpy array) '''
    with open(file, 'r') as namdinput:
        input_lines = namdinput.readlines()
        line_count = 0
        for line in input_lines:
            line_count += 1
            
            # the first line of namd input file contains the number
            # of atoms and point charges
            if line_count == 1:
                atom_pcharge_num = line.strip().split()
                # atom number
                atom_num = int(atom_pcharge_num[0])
                # point charge number
                pcharge_num = int(atom_pcharge_num[1])
                element = [None for i in range(atom_num)]
                coor = np.zeros((atom_num,3))
                pcharge = np.zeros((pcharge_num,4))
            
            # the second part contains the atom information
            if line_count > 1 and line_count <= atom_num + 1:
                atom_data = line.strip().split()
                # coordinates
                for i in range(3):
                    coor[line_count - 2,i] = float(atom_data[i])
                # elements
                element[line_count - 2] = atom_data[3]
            
            # the third part, point charge information
            if line_count > 1 + atom_num and line_count <= 1 + atom_num + pcharge_num:
                pcharge_data = line.strip().split()
                # point charge
                pcharge[line_count - 2 - atom_num, 0] = pcharge_data[3]
                # coordinates
                for i in range(3):
                    # xtb needs unit of Bohr in pcharge format
                    pcharge[line_count - 2 - atom_num, i + 1] = float(pcharge_data[i]) * 1.88973
                
    return (element, coor, pcharge)

def write_xtbinput(xyzfile, pchargefile, element, coor, pcharge):
    ''' write xtb qmmm input file based on:
        qm atom -- element (python array)
        atomic coordinates -- coor (n * 3D numpy array)
        point charge + coor -- pcharge (n * 4D numpy array)
        
        need the directory of:
        the file about atom information -- xyzfile
        ... about point charge information -- pchargefile'''
    # xtb needs a xyz as input file
    with open(xyzfile, 'w') as xyz:
        xyz.write(str(len(element)))
        xyz.write('\n\n')
        for i in range(len(element)):
            xyz.write('{} {:.6f} {:.6f} {:.6f}\n'.format(element[i], coor[i,0], coor[i,1], coor[i,2]))
    
    # pcharge file
    with open(pchargefile, 'w') as pc:
        pc.write(str(len(pcharge)))
        pc.write('\n')
        for i in range(len(pcharge)):
            pc.write('{:.6f} {:.6f} {:.6f} {:.6f}\n'.format(pcharge[i,0], 
                     pcharge[i,1], 
                     pcharge[i,2],
                     pcharge[i,3]))
            
def convert_input(namdinput, xtbinput_xyz, xtbinput_pc):
    ''' convert namdinput to xtb input '''
    element, coor, pcharge = read_namdinput(namdinput)
    write_xtbinput(xtbinput_xyz, xtbinput_pc, element, coor, pcharge)
    
def read_xtboutput(charge_file, grad_file):
    ''' read xtb qmmm output file (charge_file, grad_file)
        return:
        energy (python float)
        force + charge -- info (n * 4D numpy array) '''
    # read charge file and get the number of atoms
    atom_charge = []
    with open(charge_file, 'r') as charge:
        charge_lines = charge.readlines()
        for line in charge_lines:
            if line.strip():
                atom_charge.append(float(line.strip()))
    atom_num = len(atom_charge)
    info = np.zeros((atom_num,4))
    
    # read info
    with open(grad_file, 'r') as grad:
        grad_lines = grad.readlines()
        count = 0
        for line in grad_lines:
            count += 1
            # the first line is useless
            if count == 1:
                continue
            # the second line contains the energy
            if count == 2:
                data = line.strip().split()
                # the unit of energy in xtb is hartrees
                energy = float(data[6]) * 630
            if count > atom_num + 2 and count <= atom_num + atom_num + 2:
                data = line.strip().split()
                # force
                for i in range(3):
                    # the unit of grad in xtb output should be hartrees/bohr
                    info[count - atom_num - 2 - 1, i] = float(data[i].replace('D','E')) * (-630) * 1.88973
                info[count - atom_num - 2 - 1, 3] = atom_charge[count - atom_num - 2 - 1]
    return energy, info

def write_namdoutput(file, energy, info):
    ''' write namd qmmm output file based on:
        energy (python float)
        force + charge -- info (n * 4D numpy array)
        
        need the directory of:
        the file read by namd -- file'''
    with open(file, 'w') as namdoutput:
        namdoutput.write('{:.6f}\n'.format(energy))
        for i in range(len(info)):
            namdoutput.write('{:.6f} {:.6f} {:.6f} {:.6f}\n'.format(
                    info[i,0], info[i,1], info[i,2], info[i,3]))
            
def convert_output(xtboutput_charge, xtboutput_grad, namdoutput):
    ''' convert xtb output to namd output '''
    energy, info = read_xtboutput(xtboutput_charge, xtboutput_grad)
    write_namdoutput(namdoutput, energy, info)

def run_qmmm(directory, stdoutput):
    ''' the main function called by namd every step,
        the complete directory of the input file -- directory
        a file to record useless information to prevent from
        too many things in namd log file -- stdoutput'''
    path = os.path.dirname(directory)
    base = os.path.basename(directory)
    # namd deal with different qm part independently
    # one can set qm charge of each part
    qmpart = int(path.split('/')[-1])
    xtbxyz = path + r'/xtbxyz.xyz'
    xtbpcfile = path + r'/pcharge'
    xtbcharges = path + r'/charges'
    xtbgrad = path + r'/gradient'
    xtbrestart = path + r'/xtbrestart'
    namdoutput = path + r'/' + base + '.result'
    convert_input(directory, xtbxyz, xtbpcfile)
    subprocess.call([XTBDIR, xtbxyz, '-grad', '-charge', str(QMCHARGE[qmpart])],
                     stdout = stdoutput)
    convert_output(xtbcharges, xtbgrad, namdoutput)
    # otherwise xtb will restart a run
    os.remove(xtbxyz)
    os.remove(xtbpcfile)
    os.remove(xtbcharges)
    os.remove(xtbgrad)
    os.remove(xtbrestart)
    
if __name__ == '__main__':
    useless = open(os.path.dirname(sys.argv[1]) + r'/useless.log', 'w')
    run_qmmm(sys.argv[1], useless)
    useless.close()