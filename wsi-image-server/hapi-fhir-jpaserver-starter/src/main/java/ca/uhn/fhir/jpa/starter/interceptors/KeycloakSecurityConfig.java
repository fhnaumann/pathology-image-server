/*
 * Copyright 2021 Ona Systems, Inc
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *       http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package ca.uhn.fhir.jpa.starter.interceptors;

import static org.springframework.http.HttpMethod.DELETE;
import static org.springframework.http.HttpMethod.GET;
import static org.springframework.http.HttpMethod.POST;
import static org.springframework.http.HttpMethod.PUT;

import java.security.Principal;
import java.util.Arrays;

import org.keycloak.KeycloakPrincipal;
import org.keycloak.KeycloakSecurityContext;
import org.keycloak.adapters.KeycloakConfigResolver;
import org.keycloak.adapters.springboot.KeycloakSpringBootConfigResolver;
import org.keycloak.adapters.springsecurity.KeycloakConfiguration;
import org.keycloak.adapters.springsecurity.authentication.KeycloakAuthenticationProvider;
import org.keycloak.adapters.springsecurity.client.KeycloakClientRequestFactory;
import org.keycloak.adapters.springsecurity.client.KeycloakRestTemplate;
import org.keycloak.adapters.springsecurity.config.KeycloakWebSecurityConfigurerAdapter;
import org.keycloak.adapters.springsecurity.token.KeycloakAuthenticationToken;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.config.ConfigurableBeanFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Scope;
import org.springframework.context.annotation.ScopedProxyMode;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.authentication.builders.AuthenticationManagerBuilder;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.builders.WebSecurity;
import org.springframework.security.core.authority.mapping.SimpleAuthorityMapper;
import org.springframework.security.core.session.SessionRegistryImpl;
import org.springframework.security.web.authentication.session.NullAuthenticatedSessionStrategy;
import org.springframework.security.web.authentication.session.RegisterSessionAuthenticationStrategy;
import org.springframework.security.web.authentication.session.SessionAuthenticationStrategy;
import org.springframework.security.web.util.matcher.AntPathRequestMatcher;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.context.WebApplicationContext;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

@ConditionalOnProperty(prefix = "keycloak", name = "enabled", havingValue = "true", matchIfMissing = true)
@KeycloakConfiguration
public class KeycloakSecurityConfig extends KeycloakWebSecurityConfigurerAdapter {

	private static final String CORS_ALLOWED_HEADERS =
		"origin,content-type,accept,x-requested-with,Authorization";

	private String opensrpAllowedSources = "*";

	private long corsMaxAge = 60;

	private static final Logger logger = LoggerFactory.getLogger(KeycloakSecurityConfig.class);

	@Autowired private KeycloakClientRequestFactory keycloakClientRequestFactory;

	/**
	 * Allows to inject requests scoped wrapper for {@link KeycloakSecurityContext}.
	 *
	 * Returns the {@link KeycloakSecurityContext} from the Spring
	 * {@link ServletRequestAttributes}'s {@link Principal}.
	 * <p>
	 * The principal must support retrieval of the KeycloakSecurityContext, so at
	 * this point, only {@link KeycloakPrincipal} values and
	 * {@link KeycloakAuthenticationToken} are supported.
	 *
	 * @return the current <code>KeycloakSecurityContext</code>
	 */
	@Bean
	@Scope(scopeName = WebApplicationContext.SCOPE_REQUEST, proxyMode = ScopedProxyMode.TARGET_CLASS)
	public KeycloakSecurityContext provideKeycloakSecurityContext() {

		ServletRequestAttributes attributes = (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
		Principal principal = attributes.getRequest().getUserPrincipal();
		if (principal == null) {
			return null;
		}

		if (principal instanceof KeycloakAuthenticationToken) {
			principal = Principal.class.cast(KeycloakAuthenticationToken.class.cast(principal).getPrincipal());
		}

		if (principal instanceof KeycloakPrincipal) {
			return KeycloakPrincipal.class.cast(principal).getKeycloakSecurityContext();
		}

		return null;
	}

	@Autowired
	public void configureGlobal(AuthenticationManagerBuilder auth) {
		logger.info("CONFIGURING GLOBAL");
		SimpleAuthorityMapper grantedAuthorityMapper = new SimpleAuthorityMapper();
		grantedAuthorityMapper.setPrefix("ROLE_");

		KeycloakAuthenticationProvider keycloakAuthenticationProvider = keycloakAuthenticationProvider();
		keycloakAuthenticationProvider.setGrantedAuthoritiesMapper(new SimpleAuthorityMapper());
		auth.authenticationProvider(keycloakAuthenticationProvider);
	}

	@Override
	protected KeycloakAuthenticationProvider keycloakAuthenticationProvider() {
		logger.info("PROVIDING NEW KEYCLOAK AUTHENTICATOR");
		return new KeycloakAuthenticationProvider();
	}

	@Bean
	public KeycloakConfigResolver keycloakConfigResolver() {
		return new KeycloakSpringBootConfigResolver();
	}

	@Bean
	@Override
	protected SessionAuthenticationStrategy sessionAuthenticationStrategy() {
		return new NullAuthenticatedSessionStrategy();
		//return new RegisterSessionAuthenticationStrategy(new SessionRegistryImpl());
	}

	@Override
	protected void configure(HttpSecurity http) throws Exception {
		super.configure(http);
		logger.info("Inside configure method");
		http.cors()
			.and()
			.authorizeRequests()
			.antMatchers("/")
			.permitAll()
			.antMatchers("/home")
			.permitAll()
			.antMatchers(GET,"/fhir/Composition")
			.permitAll()
			.antMatchers(GET,"/fhir/Parameters")
			.permitAll()
			.antMatchers(GET,"/fhir/Binary")
			.permitAll()
			.mvcMatchers("/logout.do")
			.permitAll()
			.antMatchers("/fhir/**")
			.authenticated()
			.and()
			.csrf()
			.disable()
			//.ignoringAntMatchers("/fhir/**")
			//.and()
			.logout()
			.logoutRequestMatcher(new AntPathRequestMatcher("logout.do", "GET"));
	}

	@Override
	public void configure(WebSecurity web) throws Exception {
		/* @formatter:off */
		web.ignoring()
			.mvcMatchers("/js/**")
			.and()
			.ignoring()
			.mvcMatchers("/css/**")
			.and()
			.ignoring()
			.mvcMatchers("/images/**")
			.and()
			.ignoring()
			.mvcMatchers("/html/**")
			.and()
			.ignoring()
			.antMatchers(HttpMethod.OPTIONS, "/**")
			.and()
			.ignoring()
			.antMatchers("/home")
			.and()
			.ignoring()
			.antMatchers("/*")
			.and()
			.ignoring()
			.antMatchers("/fhir/metadata");
		/* @formatter:on */
	}

	@Bean
	public CorsConfigurationSource corsConfigurationSource() {
		CorsConfiguration configuration = new CorsConfiguration();
		configuration.setAllowedOrigins(Arrays.asList(opensrpAllowedSources.split(",")));
		configuration.setAllowedMethods(
			Arrays.asList(GET.name(), POST.name(), PUT.name(), DELETE.name()));
		configuration.setAllowedHeaders(Arrays.asList(CORS_ALLOWED_HEADERS.split(",")));
		configuration.setMaxAge(corsMaxAge);
		UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
		source.registerCorsConfiguration("/**", configuration);
		return source;
	}


	@Bean
	@Scope(ConfigurableBeanFactory.SCOPE_PROTOTYPE)
	public KeycloakRestTemplate keycloakRestTemplate() {
		logger.info("new kc rest template");
		return new KeycloakRestTemplate(keycloakClientRequestFactory);
	}
}