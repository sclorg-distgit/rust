%if %defined scl
%scl_package rust
%global scl_llvm llvm-toolset-7
%global scl_llvm_prefix %{scl_llvm}-
%else
%global pkg_name rust
%endif

# Only x86_64 and i686 are Tier 1 platforms at this time.
# https://forge.rust-lang.org/platform-support.html
#global rust_arches x86_64 i686 armv7hl aarch64 ppc64 ppc64le s390x
%global rust_arches x86_64 i686 aarch64 ppc64 ppc64le s390x

# The channel can be stable, beta, or nightly
%{!?channel: %global channel stable}

# To bootstrap from scratch, set the channel and date from src/stage0.txt
# e.g. 1.10.0 wants rustc: 1.9.0-2016-05-24
# or nightly wants some beta-YYYY-MM-DD
# TEMP: using the current version to bootstrap rust-toolset
#global bootstrap_rust 1.16.0
%global bootstrap_rust 1.17.0
%global bootstrap_cargo 0.17.0
%global bootstrap_channel %{bootstrap_rust}
#global bootstrap_date 2017-03-11
%global bootstrap_date 2017-04-27

# Only the specified arches will use bootstrap binaries.
%global bootstrap_arches %%{rust_arches}

# We generally don't want llvm-static present at all, since llvm-config will
# make us link statically.  But we can opt in, e.g. to aid LLVM rebases.
# FIXME: LLVM 3.9 prefers shared linking now! Which is good, but next time we
# *want* static we'll have to force it with "llvm-config --link-static".
# See also https://github.com/rust-lang/rust/issues/36854
# The new rustbuild accepts `--enable-llvm-link-shared`, else links static.
%bcond_with llvm_static

# We can also choose to just use Rust's bundled LLVM, in case the system LLVM
# is insufficient.  Rust currently requires LLVM 3.7+.
%if 0%{?rhel} && !0%{?epel}
%bcond_without bundled_llvm
%else
%bcond_with bundled_llvm
%endif

# LLDB only works on some architectures
%ifarch %{arm} aarch64 %{ix86} x86_64
# LLDB isn't available everywhere...
%if !0%{?rhel}
%bcond_without lldb
%else
%bcond_with lldb
%endif
%else
%bcond_with lldb
%endif



Name:           %{?scl_prefix}rust
Version:        1.17.0
Release:        1%{?dist}
Summary:        The Rust Programming Language
License:        (ASL 2.0 or MIT) and (BSD and ISC and MIT)
# ^ written as: (rust itself) and (bundled libraries)
URL:            https://www.rust-lang.org
ExclusiveArch:  %{rust_arches}

%if "%{channel}" == "stable"
%global rustc_package rustc-%{version}-src
%else
%global rustc_package rustc-%{channel}-src
%endif
Source0:        https://static.rust-lang.org/dist/%{rustc_package}.tar.gz

# Don't let configure clobber our debuginfo choice for stable releases.
Patch1:         rust-1.16.0-configure-no-override.patch

# Make sure LD_LIBRARY_PATH is just extended, not replaced.
Patch2:         rust-1.17.0-configure-libpath.patch

# kernel rh1410097 causes too-small stacks for PIE.
Patch4:         rust-1.17.0-no-default-pie.patch

# compiletest assumes features of older stage0
Patch5:         rust-1.17.0-static_in_const.patch

# Get the Rust triple for any arch.
%{lua: function rust_triple(arch)
  local abi = "gnu"
  if arch == "armv7hl" then
    arch = "armv7"
    abi = "gnueabihf"
  elseif arch == "ppc64" then
    arch = "powerpc64"
  elseif arch == "ppc64le" then
    arch = "powerpc64le"
  end
  return arch.."-unknown-linux-"..abi
end}

%global rust_triple %{lua: print(rust_triple(rpm.expand("%{_target_cpu}")))}

%if %defined bootstrap_arches
# For each bootstrap arch, add an additional binary Source.
# Also define bootstrap_source just for the current target.
%{lua: do
  local bootstrap_arches = {}
  for arch in string.gmatch(rpm.expand("%{bootstrap_arches}"), "%S+") do
    table.insert(bootstrap_arches, arch)
  end
  local base = rpm.expand("https://static.rust-lang.org/dist/%{bootstrap_date}"
                          .."/rust-%{bootstrap_channel}")
  local target_arch = rpm.expand("%{_target_cpu}")
  for i, arch in ipairs(bootstrap_arches) do
    print(string.format("Source%d: %s-%s.tar.gz\n",
                        i, base, rust_triple(arch)))
    if arch == target_arch then
      rpm.define("bootstrap_source "..i)
    end
  end
end}
%endif

%ifarch %{bootstrap_arches}
%global bootstrap_root rust-%{bootstrap_channel}-%{rust_triple}
%global local_rust_root %{_builddir}/%{bootstrap_root}/usr
Provides:       bundled(%{pkg_name}-bootstrap) = %{bootstrap_rust}
%else
BuildRequires:  %{?scl_prefix}cargo >= %{bootstrap_cargo}
BuildRequires:  %{name} >= %{bootstrap_rust}
BuildConflicts: %{name} > %{version}
%global local_rust_root %{_prefix}
%endif

BuildRequires:  make
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  ncurses-devel
BuildRequires:  zlib-devel
BuildRequires:  python2
BuildRequires:  curl

%if %with bundled_llvm
BuildRequires:  %{?scl_llvm_prefix}cmake3
Provides:       bundled(llvm) = 3.9
%else
%if 0%{?fedora} >= 26 || 0%{?epel}
%global llvm llvm3.9
%global llvm_root %{_libdir}/%{llvm}
%else
%global llvm llvm
%global llvm_root %{_prefix}
%endif
BuildRequires:  %{llvm}-devel >= 3.7
%if %with llvm_static
BuildRequires:  %{llvm}-static
BuildRequires:  libffi-devel
%else
# Make sure llvm-config doesn't see it.
BuildConflicts: %{llvm}-static
%endif
%endif

# make check needs "ps" for src/test/run-pass/wait-forked-but-failed-child.rs
BuildRequires:  procps-ng

# debuginfo-gdb tests need gdb
BuildRequires:  gdb

# TODO: work on unbundling these!
Provides:       bundled(hoedown) = 3.0.5
Provides:       bundled(jquery) = 2.1.4
Provides:       bundled(libbacktrace) = 6.1.0
Provides:       bundled(miniz) = 1.14

# Virtual provides for folks who attempt "dnf install rustc"
Provides:       %{?scl_prefix}rustc = %{version}-%{release}
Provides:       %{?scl_prefix}rustc%{?_isa} = %{version}-%{release}

# Always require our exact standard library
Requires:       %{name}-std-static%{?_isa} = %{version}-%{release}

# The C compiler is needed at runtime just for linking.  Someday rustc might
# invoke the linker directly, and then we'll only need binutils.
# https://github.com/rust-lang/rust/issues/11937
Requires:       gcc

%if 0%{?fedora} >= 26
# Only non-bootstrap builds should require rust-rpm-macros, because that
# requires cargo, which might not exist yet.
%ifnarch %{bootstrap_arches}
Requires:       rust-rpm-macros
%endif
%endif

%{?scl:Requires:%scl_runtime}

# ALL Rust libraries are private, because they don't keep an ABI.
%global _privatelibs lib.*-[[:xdigit:]]*[.]so.*
%global __provides_exclude ^(%{_privatelibs})$
%global __requires_exclude ^(%{_privatelibs})$
%global __provides_exclude_from ^%{_docdir}/.*$
%global __requires_exclude_from ^%{_docdir}/.*$

# While we don't want to encourage dynamic linking to Rust shared libraries, as
# there's no stable ABI, we still need the unallocated metadata (.rustc) to
# support custom-derive plugins like #[proc_macro_derive(Foo)].  But eu-strip is
# very eager by default, so we have to limit it to -g, only debugging symbols.
%global _find_debuginfo_opts -g
%undefine _include_minidebuginfo

# Use hardening ldflags.
%global rustflags -Clink-arg=-Wl,-z,relro,-z,now

%if %{without bundled_llvm} && "%{llvm_root}" != "%{_prefix}"
# https://github.com/rust-lang/rust/issues/40717
%global rustflags %{?rustflags} -Clink-arg=-L%{llvm_root}/lib
%endif

%description
Rust is a systems programming language that runs blazingly fast, prevents
segfaults, and guarantees thread safety.

This package includes the Rust compiler and documentation generator.


%package std-static
Summary:        Standard library for Rust

%description std-static
This package includes the standard libraries for building applications
written in Rust.


%package debugger-common
Summary:        Common debugger pretty printers for Rust
BuildArch:      noarch

%description debugger-common
This package includes the common functionality for %{name}-gdb and %{name}-lldb.


%package gdb
Summary:        GDB pretty printers for Rust
BuildArch:      noarch
Requires:       gdb
Requires:       %{name}-debugger-common = %{version}-%{release}

%description gdb
This package includes the rust-gdb script, which allows easier debugging of Rust
programs.


%if %with lldb

%package lldb
Summary:        LLDB pretty printers for Rust

# It could be noarch, but lldb has limited availability
#BuildArch:      noarch

Requires:       lldb
Requires:       python-lldb
Requires:       %{name}-debugger-common = %{version}-%{release}

%description lldb
This package includes the rust-lldb script, which allows easier debugging of Rust
programs.

%endif


%package doc
Summary:        Documentation for Rust
# NOT BuildArch:      noarch
# Note, while docs are mostly noarch, some things do vary by target_arch.
# Koji will fail the build in rpmdiff if two architectures build a noarch
# subpackage differently, so instead we have to keep its arch.

%description doc
This package includes HTML documentation for the Rust programming language and
its standard library.


%prep

%ifarch %{bootstrap_arches}
%setup -q -n %{bootstrap_root} -T -b %{bootstrap_source}
./install.sh --components=cargo,rustc,rust-std-%{rust_triple} \
  --prefix=%{local_rust_root} --disable-ldconfig
test -f '%{local_rust_root}/bin/cargo'
test -f '%{local_rust_root}/bin/rustc'
%endif

%setup -q -n %{rustc_package}

# unbundle
rm -rf src/jemalloc/
%if %without bundled_llvm
rm -rf src/llvm/
%endif

# extract bundled licenses for packaging
cp src/rt/hoedown/LICENSE src/rt/hoedown/LICENSE-hoedown
sed -e '/*\//q' src/libbacktrace/backtrace.h \
  >src/libbacktrace/LICENSE-libbacktrace

# These tests assume that alloc_jemalloc is present
# https://github.com/rust-lang/rust/issues/35017
sed -i.jemalloc -e '1i // ignore-test jemalloc is disabled' \
  src/test/compile-fail/allocator-dylib-is-system.rs \
  src/test/compile-fail/allocator-rust-dylib-is-jemalloc.rs \
  src/test/run-pass/allocator-default.rs

%if %{with bundled_llvm} && 0%{?epel}
mkdir -p cmake-bin
ln -s /usr/bin/cmake3 cmake-bin/cmake
%global cmake_path $PWD/cmake-bin
%endif

%if %{without bundled_llvm} && %{with llvm_static}
# Static linking to distro LLVM needs to add -lffi
# https://github.com/rust-lang/rust/issues/34486
sed -i.ffi -e '$a #[link(name = "ffi")] extern {}' \
  src/librustc_llvm/lib.rs
%endif

%patch1 -p1 -b .no-override
%patch2 -p1 -b .libpath
%patch4 -p1 -b .no-pie
%patch5 -p1 -b .static_in_const


%build

# Log some basic hw info to help diagnose failures
(set +e ; lscpu ; free ; df -h . ; echo)

%{?cmake_path:export PATH=%{cmake_path}:$PATH}
%{?rustflags:export RUSTFLAGS="%{rustflags}"}

# We're going to override --libdir when configuring to get rustlib into a
# common path, but we'll fix the shared libraries during install.
%global common_libdir %{_prefix}/lib
%global rustlibdir %{common_libdir}/rustlib

%{?scl:scl enable %scl - << \EOF}
set -ex

%configure --disable-option-checking \
  --libdir=%{common_libdir} \
  --build=%{rust_triple} --host=%{rust_triple} --target=%{rust_triple} \
  --enable-local-rust --local-rust-root=%{local_rust_root} \
  %{!?with_bundled_llvm: --llvm-root=%{llvm_root} --disable-codegen-tests \
    %{!?with_llvm_static: --enable-llvm-link-shared } } \
  --disable-jemalloc \
  --disable-rpath \
  --enable-debuginfo \
  --enable-vendor \
  --release-channel=%{channel}

./x.py dist

%{?scl:EOF}


%install
%{?cmake_path:export PATH=%{cmake_path}:$PATH}
%{?rustflags:export RUSTFLAGS="%{rustflags}"}

%{?scl:scl enable %scl - << \EOF}
set -ex

DESTDIR=%{buildroot} ./x.py dist --install

%{?scl:EOF}


# Make sure the shared libraries are in the proper libdir
%if "%{_libdir}" != "%{common_libdir}"
mkdir -p %{buildroot}%{_libdir}
find %{buildroot}%{common_libdir} -maxdepth 1 -type f -name '*.so' \
  -exec mv -v -t %{buildroot}%{_libdir} '{}' '+'
%endif

# The shared libraries should be executable for debuginfo extraction.
find %{buildroot}%{_libdir} -maxdepth 1 -type f -name '*.so' \
  -exec chmod -v +x '{}' '+'

# The libdir libraries are identical to those under rustlib/.  It's easier on
# library loading if we keep them in libdir, but we do need them in rustlib/
# to support dynamic linking for compiler plugins, so we'll symlink.
(cd "%{buildroot}%{rustlibdir}/%{rust_triple}/lib" &&
 find ../../../../%{_lib} -maxdepth 1 -name '*.so' \
   -exec ln -v -f -s -t . '{}' '+')

# Remove installer artifacts (manifests, uninstall scripts, etc.)
find %{buildroot}%{rustlibdir} -maxdepth 1 -type f -exec rm -v '{}' '+'

# FIXME: __os_install_post will strip the rlibs
# -- should we find a way to preserve debuginfo?

# Remove unwanted documentation files (we already package them)
rm -f %{buildroot}%{_docdir}/%{pkg_name}/README.md
rm -f %{buildroot}%{_docdir}/%{pkg_name}/COPYRIGHT
rm -f %{buildroot}%{_docdir}/%{pkg_name}/LICENSE-APACHE
rm -f %{buildroot}%{_docdir}/%{pkg_name}/LICENSE-MIT

# Sanitize the HTML documentation
find %{buildroot}%{_docdir}/%{pkg_name}/html -empty -delete
find %{buildroot}%{_docdir}/%{pkg_name}/html -type f -exec chmod -x '{}' '+'

%if %without lldb
rm -f %{buildroot}%{_bindir}/%{pkg_name}-lldb
rm -f %{buildroot}%{rustlibdir}/etc/lldb_*.py*
%endif


%check
%{?cmake_path:export PATH=%{cmake_path}:$PATH}
%{?rustflags:export RUSTFLAGS="%{rustflags}"}

%{?scl:scl enable %scl - << \EOF}
set -ex

# The results are not stable on koji, so mask errors and just log it.
./x.py test || :

%{?scl:EOF}


%post -p /sbin/ldconfig
%postun -p /sbin/ldconfig


%files
%license COPYRIGHT LICENSE-APACHE LICENSE-MIT
%license src/libbacktrace/LICENSE-libbacktrace
%license src/rt/hoedown/LICENSE-hoedown
%doc README.md
%{_bindir}/rustc
%{_bindir}/rustdoc
%{_libdir}/*.so
%{_mandir}/man1/rustc.1*
%{_mandir}/man1/rustdoc.1*
%dir %{rustlibdir}
%dir %{rustlibdir}/%{rust_triple}
%dir %{rustlibdir}/%{rust_triple}/lib
%{rustlibdir}/%{rust_triple}/lib/*.so


%files std-static
%dir %{rustlibdir}
%dir %{rustlibdir}/%{rust_triple}
%dir %{rustlibdir}/%{rust_triple}/lib
%{rustlibdir}/%{rust_triple}/lib/*.rlib


%files debugger-common
%dir %{rustlibdir}
%dir %{rustlibdir}/etc
%{rustlibdir}/etc/debugger_*.py*


%files gdb
%{_bindir}/rust-gdb
%{rustlibdir}/etc/gdb_*.py*


%if %with lldb
%files lldb
%{_bindir}/rust-lldb
%{rustlibdir}/etc/lldb_*.py*
%endif


%files doc
%docdir %{_docdir}/%{pkg_name}
%dir %{_docdir}/%{pkg_name}
%dir %{_docdir}/%{pkg_name}/html
%{_docdir}/%{pkg_name}/html/*/
%{_docdir}/%{pkg_name}/html/*.html
%{_docdir}/%{pkg_name}/html/*.css
%{_docdir}/%{pkg_name}/html/*.js
%{_docdir}/%{pkg_name}/html/*.woff
%license %{_docdir}/%{pkg_name}/html/*.txt


%changelog
* Fri Jun 02 2017 Josh Stone <jistone@redhat.com> - 1.17.0-1
- Bootstrap with the new SCL name.
