import ctypes
from mpi4py import MPI
import numpy as nm
import re

AUX_LENGTH = 16 * 1024
MIN_SUPPORTED_VERSION = '4.10.0'
MAX_SUPPORTED_VERSION = '5.7.999'

c_pointer = ctypes.POINTER

mumps_int = ctypes.c_int
mumps_pint = c_pointer(mumps_int)
mumps_int8 = ctypes.c_uint64
mumps_real = ctypes.c_double
mumps_preal = c_pointer(mumps_real)
mumps_complex = ctypes.c_double
mumps_pcomplex = c_pointer(mumps_complex)

mumps_libs = {}


def dec(val, encoding='utf-8'):
    """Decode given bytes using the specified encoding."""
    import sys
    if isinstance(val, bytes) and sys.version_info > (3, 0):
        val = val.decode(encoding)
    return val


def load_library(libname):
    """Load shared library in a system dependent way."""
    import sys

    if sys.platform.startswith('win'):  # Windows system
        from ctypes.util import find_library

        lib_fname = find_library(libname)
        if lib_fname is None:
            lib_fname = find_library('lib' + libname)

    else:  # Linux system
        lib_fname = 'lib' + libname + '.so'

    lib = ctypes.cdll.LoadLibrary(lib_fname)

    return lib


def load_mumps_libraries():
    mumps_libs['dmumps'] = load_library('dmumps').dmumps_c
    mumps_libs['zmumps'] = load_library('zmumps').zmumps_c


def coo_is_symmetric(mtx, tol=1e-9):
    """Check sparse matrix symmetry."""
    a_at = mtx - mtx.T

    if a_at.nnz == 0 or nm.all(nm.abs(a_at.data) < tol):
        return True

    norm = nm.linalg.norm(mtx.data)
    if nm.all(nm.abs(a_at.data) < tol * norm):
        return True

    return False


mumps_c_fields = [  # MUMPS 4.10.0
    ('sym', mumps_int),
    ('par', mumps_int),
    ('job', mumps_int),
    ('comm_fortran', mumps_int),
    ('icntl', mumps_int * 40),
    ('cntl', mumps_real * 15),
    ('n', mumps_int),
    #
    ('nz_alloc', mumps_int),
    # /* Assembled entry */
    ('nz', mumps_int),
    ('irn', mumps_pint),
    ('jcn', mumps_pint),
    ('a', mumps_pcomplex),
    # /* Distributed entry */
    ('nz_loc', mumps_int),
    ('irn_loc', mumps_pint),
    ('jcn_loc', mumps_pint),
    ('a_loc', mumps_pcomplex),
    # /* Element entry */
    ('nelt', mumps_int),
    ('eltptr', mumps_pint),
    ('eltvar', mumps_pint),
    ('a_elt', mumps_pcomplex),
    # /* Ordering, if given by user */
    ('perm_in', mumps_pint),
    # /* Orderings returned to user */
    ('sym_perm', mumps_pint),
    ('uns_perm', mumps_pint),
    # /* Scaling (input only in this version) */
    ('colsca', mumps_preal),
    ('rowsca', mumps_preal),
    # /* RHS, solution, ouptput data and statistics */
    ('rhs', mumps_pcomplex),
    ('redrhs', mumps_pcomplex),
    ('rhs_sparse', mumps_pcomplex),
    ('sol_loc', mumps_pcomplex),
    ('irhs_sparse', mumps_pint),
    ('irhs_ptr', mumps_pint),
    ('isol_loc', mumps_pint),
    ('nrhs', mumps_int),
    ('lrhs', mumps_int),
    ('lredrhs', mumps_int),
    ('nz_rhs', mumps_int),
    ('lsol_loc', mumps_int),
    ('schur_mloc', mumps_int),
    ('schur_nloc', mumps_int),
    ('schur_lld', mumps_int),
    ('mblock', mumps_int),
    ('nblock', mumps_int),
    ('nprow', mumps_int),
    ('npcol', mumps_int),
    ('info', mumps_int * 40),
    ('infog', mumps_int * 40),
    ('rinfo', mumps_real * 40),
    ('rinfog', mumps_real * 40),
    # /* Null space */
    ('deficiency', mumps_int),
    ('pivnul_list', mumps_pint),
    ('mapping', mumps_pint),
    # /* Schur */
    ('size_schur', mumps_int),
    ('listvar_schur', mumps_pint),
    ('schur', mumps_pcomplex),
    # /* Internal parameters */
    ('instance_number', mumps_int),
    ('wk_user', mumps_pcomplex),
    # /* Version number:
    #  length in FORTRAN + 1 for final \0 + 1 for alignment */
    ('version_number', ctypes.c_char * 16),
    # /* For out-of-core */
    ('ooc_tmpdir', ctypes.c_char * 256),
    ('ooc_prefix', ctypes.c_char * 64),
    # /* To save the matrix in matrix market format */
    ('write_problem', ctypes.c_char * 256),
    ('lwk_user', mumps_int),
]


mumps_c_updates = {  # incremental updates related to version 4.10.0
    '5.0.0': [
        ('new_after', 'icntl', ('keep', mumps_int * 500)),
        ('new_after', 'cntl', [
            ('dkeep', mumps_real * 130),
            ('keep8', mumps_int8 * 150),
        ]),
        ('new_after', 'rowsca', [
            ('colsca_from_mumps', mumps_int),
            ('rowsca_from_mumps', mumps_int),
        ]),
        ('replace', 'version_number', ctypes.c_char * 27),
    ],
    '5.1.0': [
        ('replace', 'dkeep', mumps_real * 230),
        ('new_after', 'nz', ('nnz', mumps_int8)),
        ('new_after', 'nz_loc', ('nnz_loc', mumps_int8)),
        ('replace', 'version_number', ctypes.c_char * 32),
        ('new_after', 'lwk_user', [
            # /* For save/restore feature */
            ('save_dir', ctypes.c_char * 256),
            ('save_prefix', ctypes.c_char * 256),
        ]),
    ],
    '5.2.0': [
        ('replace', 'icntl', mumps_int * 60),
        ('new_after', 'sol_loc', ('rhs_loc', mumps_pcomplex)),
        ('new_after', 'isol_loc', ('irhs_loc', mumps_pint)),
        ('new_after', 'lsol_loc', [
            ('nloc_rhs', mumps_int),
            ('lrhs_loc', mumps_int),
        ]),
        ('replace', 'info', mumps_int * 80),
        ('replace', 'infog', mumps_int * 80),
        ('new_after', 'save_prefix', ('metis_options', mumps_int * 40)),
    ],
    '5.3.0': [
        ('new_after', 'n', ('nblk', mumps_int)),
        ('new_after', 'a_elt', [
            # /* Matrix by blocks */
            ('blkptr', mumps_pint),
            ('blkvar', mumps_pint),
        ]),
    ],
    '5.7.0': [
        ('new_after', 'npcol', ('ld_rhsintr', mumps_int)),
        ('new_after', 'mapping', ('singular_values', mumps_preal)),
        ('delete', 'instance_number'),
        ('replace', 'ooc_tmpdir', ctypes.c_char * 1024),
        ('replace', 'ooc_prefix', ctypes.c_char * 256),
        ('replace', 'write_problem', ctypes.c_char * 1024),
        ('replace', 'save_dir', ctypes.c_char * 1024),
        ('new_after', 'metis_options', ('instance_number', mumps_int)),
    ],
}


def version_to_int(v):
    """Convert version string to integer ('5.2.1' --> 5002001)."""
    return nm.sum([int(vk) * 10**(3*k)
                   for k, vk in enumerate(v.split('.')[::-1])])


def get_mumps_c_fields(version):
    """Return the MUMPS C structure for a given MUMPS version."""
    def update_fields(f, update_f):
        for uf in update_f:
            fk = [k for k, _ in f]
            idx = fk.index(uf[1])

            if uf[0] == 'replace':
                f[idx] = (uf[1], uf[2])
            elif uf[0] == 'delete':
                del f[idx]
            elif uf[0] == 'new_after':
                if isinstance(uf[2], list):
                    f[(idx + 1):(idx + 1)] = uf[2]
                else:
                    f.insert(idx + 1, uf[2])

        return f

    update_keys = list(mumps_c_updates.keys())
    update_keys.sort()

    vnum = version_to_int(version)
    if vnum < version_to_int(MIN_SUPPORTED_VERSION)


    fields = mumps_c_fields.copy()
    for ukey in update_keys:
        if version_to_int(ukey) > vnum:
            break

        fields = update_fields(fields, mumps_c_updates[ukey])

    return fields


class MumpsSolver(object):
    """MUMPS object."""

    @staticmethod
    def define_mumps_c_struc(fields):
        class mumps_c_struc(ctypes.Structure):
            _fields_ = fields

        return mumps_c_struc

    def __init__(self, is_sym=False, mpi_comm=None,
                 system='real', silent=True, mem_relax=20):
        """
        Init MUMUPS solver.

        Parameters
        ----------
        is_sym : bool
            Symmetric matrix?
        mpi_comm : MPI Communicator or None
            If None, use MPI.COMM_WORLD
        system : 'real' or 'complex'
            Use real or complex linear solver.
        silent : bool
            If True, no MUMPS error, warning, and diagnostic messages.
        mem_relax : int
            The percentage increase in the estimated working space.
        """
        self.struct = None

        if len(mumps_libs) == 0:
            load_mumps_libraries()

        if system == 'real':
            self._mumps_c = mumps_libs['dmumps']
        elif system == 'complex':
            self._mumps_c = mumps_libs['zmumps']

        self.mpi_comm = MPI.COMM_WORLD if mpi_comm is None else mpi_comm
        self._mumps_c.restype = None

        # determine mumps version
        c_fields = mumps_c_fields[:5] + [('aux', ctypes.c_uint8 * AUX_LENGTH)]
        mumps_c_struc = self.define_mumps_c_struc(c_fields)
        self._mumps_c.argtypes = [c_pointer(mumps_c_struc)]

        self.struct = mumps_c_struc()
        self.struct.par = 1
        self.struct.sym = 0
        self.struct.comm_fortran = self.mpi_comm.py2f()
        self.struct.job = -1

        self._mumps_c(ctypes.byref(self.struct))

        arr = nm.ctypeslib.as_array(self.struct.aux)
        idxs = nm.logical_and(arr >= ord('.'), arr <= ord('9'))
        s = dec(arr[idxs].tostring())
        vnums = re.findall('^.*(\d)\.(\d+)\.(\d+).*$', s)[-1]
        self.struct.job = -2

        self.set_silent()
        self._mumps_c(ctypes.byref(self.struct))

        c_fields = get_mumps_c_fields('.'.join(vnums))
        mumps_c_struc = self.define_mumps_c_struc(c_fields)

        # init mumps library
        self._mumps_c.argtypes = [c_pointer(mumps_c_struc)]

        self.struct = mumps_c_struc()
        self.struct.par = 1
        self.struct.sym = 2 if is_sym else 0
        self.struct.n = 0
        self.struct.comm_fortran = self.mpi_comm.py2f()

        self._mumps_call(job=-1)  # init

        self.rank = self.mpi_comm.rank
        self._data = {}

        # be silent
        if silent:
            self.set_silent()

        self.struct.icntl[13] = mem_relax

    def set_silent(self):
        self.struct.icntl[0] = -1  # suppress error messages
        self.struct.icntl[1] = -1  # suppress diagnostic messages
        self.struct.icntl[2] = -1  # suppress global info
        self.struct.icntl[3] = 0

    def set_verbose(self):
        self.struct.icntl[0] = 6  # error messages
        self.struct.icntl[1] = 0  # diagnostic messages
        self.struct.icntl[2] = 6  # global info
        self.struct.icntl[3] = 2

    def __del__(self):
        """Finish MUMPS."""
        if self.struct is not None:
            self._mumps_call(job=-2)  # done

        self.struct = None

    def set_mtx_centralized(self, mtx):
        """
        Set the sparse matrix.

        Parameters
        ----------
        mtx : scipy sparse martix
            The sparse matrix in COO format.
        """
        assert mtx.shape[0] == mtx.shape[1]

        rr = mtx.row + 1
        cc = mtx.col + 1
        data = mtx.data

        if self.struct.sym > 0:
            idxs = nm.where(cc >= rr)[0]  # upper triangular matrix
            rr, cc, data = rr[idxs], cc[idxs], data[idxs]

        self.set_rcd_centralized(rr, cc, data, mtx.shape[0])

    def set_rcd_centralized(self, ir, ic, data, n):
        """
        Set the matrix by row and column indicies and data vector.
        The matrix shape is determined by the maximal values of
        row and column indicies. The indices start with 1.

        Parameters
        ----------
        ir : array
            The row idicies.
        ic : array
            The column idicies.
        data : array
            The matrix entries.
        n : int
            The matrix dimension.
        """
        assert ir.shape[0] == ic.shape[0] == data.shape[0]

        self._data.update(ir=ir, ic=ic, data=data)
        self.struct.n = n
        self.struct.nz = ir.shape[0]
        if hasattr(self.struct, 'nnz'):
            self.struct.nnz = ir.shape[0]
        self.struct.irn = ir.ctypes.data_as(mumps_pint)
        self.struct.jcn = ic.ctypes.data_as(mumps_pint)
        self.struct.a = data.ctypes.data_as(mumps_pcomplex)

    def set_rhs(self, rhs):
        """Set the right hand side of the linear system."""
        self._data.update(rhs=rhs)
        self.struct.rhs = rhs.ctypes.data_as(mumps_pcomplex)

    def __call__(self, job):
        """Set the job and call MUMPS."""
        self._mumps_call(job)

    def get_schur(self, schur_list):
        """Get the Schur matrix and the condensed right-hand side vector.

        Parameters
        ----------
        schur_list : array
            The list of the Schur DOFs (indexing starts with 1).

        Returns
        -------
        schur_arr : array
            The Schur matrix of order 'schur_size'.
        schur_rhs : array
            The reduced right-hand side vector.
        """
        # Schur
        schur_size = schur_list.shape[0]
        schur_arr = nm.empty((schur_size**2, ), dtype='d')
        schur_rhs = nm.empty((schur_size, ), dtype='d')
        self._schur_rhs = schur_rhs

        self.struct.size_schur = schur_size
        self.struct.listvar_schur = schur_list.ctypes.data_as(mumps_pint)
        self.struct.schur = schur_arr.ctypes.data_as(mumps_pcomplex)
        self.struct.lredrhs = schur_size
        self.struct.redrhs = schur_rhs.ctypes.data_as(mumps_pcomplex)

        # get matrix
        self.struct.schur_lld = schur_size
        self.struct.nprow = 1
        self.struct.npcol = 1
        self.struct.mblock = 100
        self.struct.nblock = 100

        self.struct.icntl[18] = 3  # centr. Schur complement stored by columns
        self.struct.job = 4  # analyze + factorize
        self._mumps_c(ctypes.byref(self.struct))

        # get RHS
        self.struct.icntl[25] = 1  # Reduction/condensation phase
        self.struct.job = 3  # solve
        self._mumps_c(ctypes.byref(self.struct))

        return schur_arr.reshape((schur_size, schur_size)), schur_rhs

    def expand_schur(self, x2):
        """Expand to a complete solution.

        Parameters
        ----------
        x2 : array
            Partial solution

        Returns
        -------
        x : array
            Complete solution
        """
        self._schur_rhs[:] = x2
        self.struct.icntl[25] = 2  # Expansion phase
        self.struct.job = 3  # solve
        self._mumps_c(ctypes.byref(self.struct))

        return self._data['rhs']

    def _mumps_call(self, job):
        """Set the job and call MUMPS.

        Jobs:
        -----
        1: analyse
        2: factorize
        3: solve
        4: analyse, factorize
        5: factorize, solve
        6: analyse, factorize, solve
        """
        self.struct.job = job
        self._mumps_c(ctypes.byref(self.struct))

        if self.struct.infog[0] < 0:
            raise RuntimeError("MUMPS error: %d" % self.struct.infog[0])
