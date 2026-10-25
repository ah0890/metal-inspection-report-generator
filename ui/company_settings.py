"""Company letterhead settings (Settings tab), used by the covering letter."""

from __future__ import annotations

import base64

import streamlit as st

from models.letter import CompanyProfile
from services.letter_service import load_company, save_company
from ui.state import get_repository

MAX_LOGO_BYTES = 1_000_000


def render_company_settings() -> None:
    repo = get_repository()
    profile = load_company(repo)

    st.markdown("#### Company Letterhead (covering letters)")
    st.caption("Only details you enter here appear on the letterhead. Leave unavailable details "
               "blank; do not add accreditation or registration claims unless verified.")
    if st.session_state.get("company_notice"):
        st.success(st.session_state.pop("company_notice"))

    with st.form("company_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Company name *", value=profile.name, max_chars=100)
        tagline = c2.text_input("Tagline", value=profile.tagline, max_chars=100)
        address = st.text_area("Address (optional)", value=profile.address, height=68)
        c1, c2, c3 = st.columns(3)
        telephone = c1.text_input("Telephone (optional)", value=profile.telephone)
        email = c2.text_input("Email (optional)", value=profile.email)
        website = c3.text_input("Website (optional)", value=profile.website)
        c1, c2 = st.columns(2)
        signatory = c1.text_input("General Manager's name (default signatory, optional)",
                                  value=profile.signatory_name)
        designation = c2.text_input("Signatory designation", value=profile.signatory_designation)
        c1, c2 = st.columns([3, 1])
        logo = c1.file_uploader("Logo (PNG or JPEG, optional)", type=["png", "jpg", "jpeg"])
        remove_logo = c2.checkbox("Remove current logo", disabled=not profile.logo_base64)
        if profile.logo_base64:
            c2.image(base64.b64decode(profile.logo_base64), width=80)
        submitted = st.form_submit_button("Save letterhead", type="primary", icon="💾")

    if submitted:
        updated = CompanyProfile(
            name=name.strip(), tagline=tagline.strip(), address=address.strip(),
            telephone=telephone.strip(), email=email.strip(), website=website.strip(),
            signatory_name=signatory.strip(),
            signatory_designation=designation.strip() or "General Manager",
            logo_base64="" if remove_logo else profile.logo_base64,
            logo_mime="" if remove_logo else profile.logo_mime,
        )
        if logo is not None:
            data = logo.getvalue()
            if len(data) > MAX_LOGO_BYTES:
                st.error("The logo file is larger than 1 MB. Please use a smaller image.")
                return
            updated.logo_base64 = base64.b64encode(data).decode("ascii")
            updated.logo_mime = logo.type or ""
        try:
            save_company(repo, updated)
        except ValueError as e:
            st.error(str(e))
            return
        st.session_state["company_notice"] = "Letterhead saved."
        st.rerun()
